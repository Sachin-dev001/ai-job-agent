import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path for robust imports across all hosting platforms
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import shutil
import asyncio
from typing import List, Optional, Any
import json
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends, BackgroundTasks
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
from app.auth.auth_handler import get_current_user, CurrentUser
from app.database.supabase_client import cloud_db

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
COOKIES_DIR = os.path.join(PROJECT_ROOT, "backend", "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)
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
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "cloud_database": "supabase" if cloud_db.is_cloud_enabled() else "local_sqlite"
    }

# ==============================================================================
# Multi-User Authentication & Profile Endpoints
# ==============================================================================
@app.get("/api/auth/me")
async def get_auth_me(user: CurrentUser = Depends(get_current_user)):
    """Returns the authenticated user's identity and cloud status."""
    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "is_authenticated": user.is_authenticated,
        "cloud_enabled": cloud_db.is_cloud_enabled()
    }

@app.get("/api/user/profile")
async def get_user_profile(user: CurrentUser = Depends(get_current_user)):
    """Fetches user candidate profile."""
    profile = await cloud_db.get_profile(user.id)
    return profile

@app.post("/api/user/profile")
async def update_user_profile(updates: dict, user: CurrentUser = Depends(get_current_user)):
    """Updates candidate profile in Supabase/local DB."""
    success = await cloud_db.update_profile(user.id, updates)
    return {"success": success}

@app.get("/api/user/applications")
async def get_user_applications(limit: int = 50, user: CurrentUser = Depends(get_current_user)):
    """Retrieves tracked job applications for the authenticated tenant."""
    apps = await cloud_db.get_applications(user.id, limit=limit)
    return {"applications": apps}

# ==============================================================================
# Resume Analysis & Processing
# ==============================================================================
@app.post("/api/resume/analyze", response_model=ResumeAnalysisResult)
async def analyze_resume(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    global LATEST_PROFILE
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(status_code=400, detail="Only .pdf, .docx, and .txt files are supported.")

    user_upload_dir = os.path.join(UPLOAD_DIR, user.id)
    os.makedirs(user_upload_dir, exist_ok=True)
    file_path = os.path.join(user_upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = await resume_analyst.analyze(file_path)
        LATEST_PROFILE = result.dict()
        # Save extracted candidate details to profile
        cand_name = getattr(result, 'candidate_name', None) or getattr(result, 'name', None) or user.name
        cand_email = getattr(result, 'email', None) or user.email
        cand_phone = getattr(result, 'phone', None)
        cand_exp = getattr(result, 'experience_years', None) or getattr(result, 'years_of_experience', 2.0)

        if cand_name or cand_email or cand_phone:
            await cloud_db.update_profile(user.id, {
                'full_name': cand_name,
                'email': cand_email,
                'phone': cand_phone,
                'experience_years': cand_exp
            })
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
    platform: Optional[str] = "Naukri"
    job_url: str
    description: Optional[str] = ""

@app.post("/api/jobs/prepare-application")
async def prepare_application(req: ApplicationPrepRequest, user: CurrentUser = Depends(get_current_user)):
    candidate_skills = LATEST_PROFILE.get("technical_skills", ["Python", "FastAPI", "AI Agents"])
    exp_years = LATEST_PROFILE.get("years_of_experience", 2)
    role_pitch = LATEST_PROFILE.get("primary_domain", "AI/Software Engineer")

    cover_letter = await cover_letter_agent.generate_cover_letter(
        candidate_name=user.name or "Candidate",
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
async def execute_live_naukri_apply(req: LiveApplyRequest, user: CurrentUser = Depends(get_current_user)):
    """
    Launches autonomous Playwright browser, clicks real 'Apply on Naukri' buttons,
    submits real applications, and returns proof screenshots.
    """
    try:
        result = await naukri_live_runner.execute_live_apply(query=req.query, limit=req.limit)
        # Record application
        await cloud_db.create_application(user.id, {
            "platform": "naukri",
            "job_title": req.query,
            "company_name": "Naukri Matched Employer",
            "job_url": "https://www.naukri.com",
            "status": "applied" if result.get("success") else "failed",
            "match_score": 94.0
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SingleJobApplyRequest(BaseModel):
    job_url: str
    job_title: str = "AI Engineer"

@app.post("/api/naukri/apply-single")
async def apply_single_job(req: SingleJobApplyRequest, user: CurrentUser = Depends(get_current_user)):
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
async def apply_single_wellfound_job(req: WellfoundSingleApplyRequest, user: CurrentUser = Depends(get_current_user)):
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
async def execute_live_wellfound_apply(req: LiveApplyRequest, user: CurrentUser = Depends(get_current_user)):
    """
    Batch auto-apply on Wellfound startup jobs matching query.
    """
    try:
        result = await wellfound_live_runner.execute_batch_apply(query=req.query, limit=req.limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConnectCookiesRequest(BaseModel):
    platform: Optional[str] = "Naukri"
    cookies: Any

@app.get("/api/session/status")
async def get_session_status():
    naukri_cookies = naukri_live_runner._load_cookies()
    wellfound_cookies = wellfound_live_runner._load_cookies()
    return {
        "naukri_connected": len(naukri_cookies) > 0,
        "naukri_cookies_count": len(naukri_cookies),
        "wellfound_connected": len(wellfound_cookies) > 0,
        "wellfound_cookies_count": len(wellfound_cookies)
    }

@app.post("/api/session/connect-cookies")
async def connect_portal_cookies(req: ConnectCookiesRequest):
    platform = req.platform.lower().strip()
    if platform not in ["naukri", "wellfound"]:
        raise HTTPException(status_code=400, detail="Platform must be 'naukri' or 'wellfound'")

    raw = req.cookies
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="Cookies must be a list of cookie objects")

    cookie_file = os.path.join(COOKIES_DIR, f"{platform}_cookies.json")
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)

    return {
        "status": "success",
        "platform": platform,
        "cookies_count": len(raw),
        "message": f"Successfully connected {platform.capitalize()} session with {len(raw)} cookies!"
    }

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
async def get_qa_memory(user: CurrentUser = Depends(get_current_user)):
    """Returns all stored candidate memory facts for this user and any pending unanswered recruiter questions."""
    memories = await cloud_db.get_memories(user.id)
    return {
        "memories": memories,
        "pending": qa_vault.get_pending_questions()
    }

@app.post("/api/memory/qa")
async def save_qa_memory(req: QAPairRequest, user: CurrentUser = Depends(get_current_user)):
    """Saves or updates a permanent question-answer pair into candidate memory."""
    entry = await cloud_db.save_memory(
        user_id=user.id,
        question=req.question,
        answer=req.answer,
        category=req.category or "custom"
    )
    return {"status": "saved", "entry": entry}

@app.delete("/api/memory/qa/{memory_id}")
async def delete_qa_memory(memory_id: str, user: CurrentUser = Depends(get_current_user)):
    """Deletes an entry from memory."""
    success = await cloud_db.delete_memory(user_id=user.id, memory_id=memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return {"status": "deleted", "id": memory_id}

@app.post("/api/memory/answer-pending")
async def answer_pending_question(req: AnswerPendingRequest, user: CurrentUser = Depends(get_current_user)):
    """Answers a pending question from the dashboard and permanently saves it to user memory."""
    pending_items = qa_vault.get_pending_questions()
    matched = None
    for p in pending_items:
        if p.get("id") == req.question_id:
            matched = p
            break
    if not matched:
        raise HTTPException(status_code=404, detail="Pending question not found")

    await cloud_db.save_memory(
        user_id=user.id,
        question=matched["question"],
        answer=req.answer,
        category="recruiter_qa"
    )
    # Also resolve in local cache
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
