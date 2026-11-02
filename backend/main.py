import os
import shutil
import asyncio
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.agents.resume_analyst import resume_analyst
from app.agents.job_scout import job_scout
from app.agents.cover_letter_agent import cover_letter_agent
from app.agents.naukri_live_runner import naukri_live_runner
from app.agents.wellfound_live_runner import wellfound_live_runner
from app.parsers.models import ResumeAnalysisResult
from app.scrapers.base_scraper import ScrapedJob
from app.notifications.notifier import notifier
from app.memory.qa_vault import qa_vault
from app.notifications.telegram_listener import telegram_listener

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
PROOF_DIR = os.path.join(PROJECT_ROOT, "backend", "proofs")
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "backend", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROOF_DIR, exist_ok=True)

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if os.path.exists(PROOF_DIR):
    app.mount("/proofs", StaticFiles(directory=PROOF_DIR), name="proofs")

LATEST_PROFILE = {}

@app.get("/")
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Job Agent API operational."}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME, "version": settings.VERSION}

@app.post("/api/resume/analyze", response_model=ResumeAnalysisResult)
async def analyze_resume(file: UploadFile = File(...)):
    global LATEST_PROFILE
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(status_code=400, detail="Only .pdf, .docx, and .txt files are supported.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = await resume_analyst.analyze(file_path)
        LATEST_PROFILE = result.dict()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/search", response_model=List[ScrapedJob])
async def search_jobs(
    query: str = Query(..., description="Role or skill keywords"),
    platform: str = Query("all", description="naukri, wellfound, or all"),
    limit: int = Query(25, description="Max jobs to return")
):
    try:
        jobs = await job_scout.find_jobs(query=query, platform=platform, limit=limit)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ApplicationPrepRequest(BaseModel):
    job_title: str
    company: str
    platform: str
    job_url: str
    description: Optional[str] = ""

@app.post("/api/jobs/prepare-application")
async def prepare_application(req: ApplicationPrepRequest):
    candidate_skills = LATEST_PROFILE.get("technical_skills", ["Python", "FastAPI", "AI Agents"])
    exp_years = LATEST_PROFILE.get("years_of_experience", 2)
    role_pitch = LATEST_PROFILE.get("primary_domain", "AI/Software Engineer")

    cover_letter = await cover_letter_agent.generate_cover_letter(
        candidate_name="Sachin",
        candidate_skills=candidate_skills,
        experience_summary=f"{exp_years} years building production applications and autonomous AI systems.",
        target_role=req.job_title,
        target_company=req.company,
        job_description=req.description or ""
    )

    await notifier.send_cover_letter_alert(
        job_title=req.job_title,
        company=req.company,
        platform=req.platform,
        job_url=req.job_url,
        cover_letter=cover_letter
    )

    return {
        "status": "ready",
        "job_title": req.job_title,
        "company": req.company,
        "job_url": req.job_url,
        "cover_letter": cover_letter
    }

class LiveApplyRequest(BaseModel):
    query: str = "AI Engineer"
    limit: int = 3

@app.post("/api/naukri/auto-apply-live")
async def execute_live_naukri_apply(req: LiveApplyRequest):
    """
    Launches autonomous Playwright browser, clicks real 'Apply on Naukri' buttons,
    submits real applications, and returns proof screenshots.
    """
    try:
        result = await naukri_live_runner.execute_live_apply(query=req.query, limit=req.limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SingleJobApplyRequest(BaseModel):
    job_url: str
    job_title: str = "AI Engineer"

@app.post("/api/naukri/apply-single")
async def apply_single_job(req: SingleJobApplyRequest):
    """
    Directly navigates to the specified job URL, clicks Apply,
    navigates questionnaires, and saves screenshot proof.
    """
    try:
        result = await naukri_live_runner.apply_single_job(job_url=req.job_url, job_title=req.job_title)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class WellfoundSingleApplyRequest(BaseModel):
    job_url: str
    job_title: str = "Startup Role"
    company: str = "Tech Startup"

@app.post("/api/wellfound/apply-single")
async def apply_single_wellfound_job(req: WellfoundSingleApplyRequest):
    """
    Directly navigates to the specified Wellfound startup job,
    submits application with user profile & pitch, and takes screenshot proof.
    """
    try:
        result = await wellfound_live_runner.apply_single_job(
            job_url=req.job_url,
            job_title=req.job_title,
            company=req.company
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/wellfound/auto-apply-live")
async def execute_live_wellfound_apply(req: LiveApplyRequest):
    """
    Batch auto-apply on Wellfound startup jobs matching query.
    """
    try:
        result = await wellfound_live_runner.execute_batch_apply(query=req.query, limit=req.limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    # Launch Telegram Bot background listener for Human-In-The-Loop memory
    asyncio.create_task(telegram_listener.start_listening())
    print("[Main] Telegram background listener task created.")

class QAPairRequest(BaseModel):
    question: str
    answer: str
    category: Optional[str] = "custom"

class AnswerPendingRequest(BaseModel):
    question_id: str
    answer: str

class SkipPendingRequest(BaseModel):
    question_id: str

@app.get("/api/memory/qa")
async def get_qa_memory():
    """Returns all stored candidate memory facts and any pending unanswered recruiter questions."""
    return {
        "memories": qa_vault.get_all_memories(),
        "pending": qa_vault.get_pending_questions()
    }

@app.post("/api/memory/qa")
async def save_qa_memory(req: QAPairRequest):
    """Saves or updates a permanent question-answer pair into candidate memory."""
    entry = qa_vault.learn(question=req.question, answer=req.answer, category=req.category or "custom")
    return {"status": "saved", "entry": entry}

@app.delete("/api/memory/qa/{memory_id}")
async def delete_qa_memory(memory_id: str):
    """Deletes an entry from memory."""
    success = qa_vault.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return {"status": "deleted", "id": memory_id}

@app.post("/api/memory/answer-pending")
async def answer_pending_question(req: AnswerPendingRequest):
    """Answers a pending question from the dashboard and permanently saves it."""
    pending_items = qa_vault.get_pending_questions()
    matched = None
    for p in pending_items:
        if p.get("id") == req.question_id:
            matched = p
            break
    if not matched:
        raise HTTPException(status_code=404, detail="Pending question not found")

    qa_vault.learn(question=matched["question"], answer=req.answer, category="recruiter_qa")
    return {"status": "answered_and_remembered", "question": matched["question"], "answer": req.answer}

@app.post("/api/memory/skip-pending")
async def skip_pending_question(req: SkipPendingRequest):
    """Skips or dismisses a pending question so it stops blocking the UI and applicant flow."""
    success = qa_vault.skip_pending_question(req.question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending question not found")
    return {"status": "skipped", "id": req.question_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
