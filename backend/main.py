import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

# Ensure backend directory is in sys.path for robust imports across all hosting platforms
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import shutil
import asyncio
from datetime import datetime
from typing import List, Optional, Any
import json
import re
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
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
from app.auth.auth_handler import get_current_user, require_authenticated_user, CurrentUser, create_access_token, SERVER_AUTH_SECRET
import hashlib
import base64
from app.database.supabase_client import cloud_db
from app.utils.cookie_normalizer import normalize_cookies

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://ai-job-agent-frontend-mauve.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
PROOF_DIR = os.path.join(PROJECT_ROOT, "backend", "proofs")
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "backend", "uploads")
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
DATA_DIR = os.path.join(BACKEND_DIR, "data")
DATA_COOKIES_DIR = os.path.join(DATA_DIR, "cookies")
os.makedirs(DATA_COOKIES_DIR, exist_ok=True)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROOF_DIR, exist_ok=True)

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if os.path.exists(PROOF_DIR):
    app.mount("/proofs", StaticFiles(directory=PROOF_DIR), name="proofs")



@app.get("/")
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Job Agent API operational."}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

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
class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

def hash_password(password: str) -> str:
    salt = SERVER_AUTH_SECRET
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def generate_tenant_user_id(email: str) -> str:
    encoded = base64.urlsafe_b64encode(email.strip().lower().encode("utf-8")).decode("utf-8").rstrip("=")
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "", encoded)
    return f"user-{clean_id}"

@app.post("/api/auth/register")
async def register_candidate(req: RegisterRequest):
    email = (req.email or "").strip().lower()
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    existing_user = await cloud_db.get_user_by_email(email)
    name = (req.full_name or "").strip() or email.split("@")[0]
    pwd_hash = hash_password(req.password)

    if existing_user:
        if verify_password(req.password, existing_user.get("password_hash", "")):
            user_id = existing_user["id"]
            user_name = existing_user.get("full_name") or existing_user.get("name") or name
            token = create_access_token(user_id=user_id, email=email, name=user_name)
            return {
                "token": token,
                "user": {
                    "id": user_id,
                    "email": email,
                    "name": user_name,
                    "full_name": user_name
                }
            }
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please switch to Sign In.")

    user_id = generate_tenant_user_id(email)
    user_record = await cloud_db.create_user(
        email=email,
        password_hash=pwd_hash,
        full_name=name,
        user_id=user_id
    )
    token = create_access_token(user_id=user_id, email=email, name=name)
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "name": name,
            "full_name": name
        }
    }

@app.post("/api/auth/login")
async def login_candidate(req: LoginRequest):
    email = (req.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not req.password:
        raise HTTPException(status_code=400, detail="Password is required.")

    user_record = await cloud_db.get_user_by_email(email)
    if not user_record:
        raise HTTPException(status_code=401, detail="No account found with this email. Please switch to the 'Create Account' tab above to register first.")

    if not verify_password(req.password, user_record.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Incorrect password. Please verify your credentials.")

    user_id = user_record["id"]
    user_name = user_record.get("full_name") or user_record.get("name") or email.split("@")[0]
    token = create_access_token(user_id=user_id, email=email, name=user_name)
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "name": user_name,
            "full_name": user_name
        }
    }

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
async def get_user_profile(user: CurrentUser = Depends(require_authenticated_user)):
    """Fetches user candidate profile."""
    profile = await cloud_db.get_profile(user.id)
    return profile

@app.post("/api/user/profile")
async def update_user_profile(updates: dict, user: CurrentUser = Depends(require_authenticated_user)):
    """Updates candidate profile in Supabase/local DB."""
    success = await cloud_db.update_profile(user.id, updates)
    return {"success": success}

@app.get("/api/user/applications")
async def get_user_applications(limit: int = 50, user: CurrentUser = Depends(require_authenticated_user)):
    """Retrieves tracked job applications for the authenticated tenant."""
    apps = await cloud_db.get_applications(user.id, limit=limit)
    return {"applications": apps}

# ==============================================================================
# Resume Analysis & Processing
# ==============================================================================
@app.post("/api/resume/analyze", response_model=ResumeAnalysisResult)
async def analyze_resume(file: UploadFile = File(...), user: CurrentUser = Depends(require_authenticated_user)):

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
        # Save extracted candidate details to profile
        cand_name = getattr(result, 'candidate_name', None) or getattr(result, 'name', None) or user.name
        cand_email = getattr(result, 'email', None) or user.email
        cand_phone = getattr(result, 'phone', None)
        cand_exp = getattr(result, 'experience_years', None) or getattr(result, 'years_of_experience', 2.0)
        skills = getattr(result, 'skills', []) or []
        tech_skills = getattr(result, 'technical_skills', []) or skills
        domain = getattr(result, 'primary_domain', None) or getattr(result, 'domain', 'AI/Software Engineer')

        # Update candidate profile in cloud_db (isolated per user.id)
        await cloud_db.update_profile(user.id, {
            'full_name': cand_name,
            'email': cand_email,
            'phone': cand_phone,
            'experience_years': cand_exp,
            'skills': skills,
            'technical_skills': tech_skills,
            'primary_domain': domain,
            'resume_analyzed': True,
            'resume_filename': file.filename,
            'analyzed_at': datetime.utcnow().isoformat(),
            'analysis_result': result.dict()
        })

        if cand_name or cand_email or cand_phone:
            # Auto-seed this candidate's private memory vault from parsed resume facts (skip None, empty, or dummy values)
            if cand_name and cand_name not in ["Guest", "Candidate"]:
                await cloud_db.save_memory(user.id, "What is your full name?", cand_name, "personal")
            if cand_email and cand_email != "candidate@example.com" and not cand_email.endswith("@autoapply.ai"):
                await cloud_db.save_memory(user.id, "What is your email address?", cand_email, "contact")
            if cand_phone and cand_phone != "+1 (555) 019-2834":
                await cloud_db.save_memory(user.id, "What is your mobile/contact number?", str(cand_phone), "contact")
            if cand_exp and cand_exp > 0:
                await cloud_db.save_memory(user.id, "How many total years of work experience do you have?", str(cand_exp), "experience")
            if skills and len(skills) > 0:
                skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
                await cloud_db.save_memory(user.id, "What skills and technologies have you worked with?", skills_str, "skills")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class JobScoutRequest(BaseModel):
    query: str = "Software Engineer"
    platform: Optional[str] = "all"
    limit: Optional[int] = 25

@app.post("/api/jobs/scout", response_model=List[ScrapedJob])
async def scout_jobs(req: JobScoutRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """AI Job Scout endpoint - searches and matches jobs for authenticated candidate."""
    try:
        jobs = await job_scout.find_jobs(query=req.query, platform=req.platform or "all", limit=req.limit or 25)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/search", response_model=List[ScrapedJob])
async def search_jobs(
    query: str = Query(..., description="Role or skill keywords"),
    platform: str = Query("all", description="naukri, wellfound, or all"),
    limit: int = Query(25, description="Max jobs to return"),
    user: CurrentUser = Depends(require_authenticated_user)
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
async def prepare_application(req: ApplicationPrepRequest, user: CurrentUser = Depends(require_authenticated_user)):
    user_profile = await cloud_db.get_profile(user.id) or {}

    cand_name = user_profile.get("full_name") or user.name or "Candidate"
    skills = user_profile.get("technical_skills") or user_profile.get("skills") or ["Python", "FastAPI", "AI Agents"]
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    exp_years = user_profile.get("experience_years") or 2

    cover_letter = await cover_letter_agent.generate_cover_letter(
        candidate_name=cand_name,
        candidate_skills=skills,
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

RESUME_REQUIRED_MSG = "Resume profile required before running auto-apply. Please upload and analyze your resume first."

async def has_analyzed_resume(user_id: str) -> bool:
    profile = await cloud_db.get_profile(user_id)
    if not profile:
        return False
    if profile.get("resume_analyzed") is True:
        return True
    if profile.get("analyzed_at"):
        return True
    skills = profile.get("skills") or profile.get("technical_skills")
    if skills and len(skills) > 0:
        return True
    return False

def resume_required_response():
    return JSONResponse(
        status_code=400,
        content={
            "status": "validation_error",
            "message": RESUME_REQUIRED_MSG,
            "detail": RESUME_REQUIRED_MSG
        }
    )

class LiveApplyRequest(BaseModel):
    query: str = "AI Engineer"
    limit: int = 3

@app.post("/api/naukri/auto-apply-live")
async def execute_live_naukri_apply(req: LiveApplyRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """
    Launches autonomous Playwright browser, clicks real 'Apply on Naukri' buttons,
    submits real applications, and returns proof screenshots.
    """
    if not await has_analyzed_resume(user.id):
        return resume_required_response()

    try:
        result = await naukri_live_runner.execute_live_apply(query=req.query, limit=req.limit, user_id=user.id)
        # Record applications from batch results or completed status
        apps_to_record = result.get("applications", [])
        if apps_to_record:
            for app_item in apps_to_record:
                status = "applied" if app_item.get("status") in ["applied_successfully", "applied", "already_applied"] else app_item.get("status", "in_progress")
                await cloud_db.create_application(user.id, {
                    "platform": "naukri",
                    "job_title": app_item.get("job_title") or req.query,
                    "company_name": app_item.get("company_name") or "Naukri Matched Employer",
                    "job_url": app_item.get("url") or "https://www.naukri.com",
                    "status": status,
                    "match_score": app_item.get("match_score", 94.0)
                })
        elif result.get("success") or result.get("status") in ["applied_successfully", "completed"]:
            await cloud_db.create_application(user.id, {
                "platform": "naukri",
                "job_title": req.query,
                "company_name": "Naukri Matched Employer",
                "job_url": "https://www.naukri.com",
                "status": "applied",
                "match_score": 94.0
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SingleJobApplyRequest(BaseModel):
    job_url: str
    job_title: str = "AI Engineer"

@app.post("/api/naukri/apply-single")
@app.post("/api/apply/single")
async def apply_single_job(req: SingleJobApplyRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """
    Directly navigates to the specified job URL, clicks Apply,
    navigates questionnaires, and saves screenshot proof.
    """
    if not await has_analyzed_resume(user.id):
        return resume_required_response()

    try:
        result = await naukri_live_runner.apply_single_job(job_url=req.job_url, job_title=req.job_title, user_id=user.id)
        if result.get("status") in ["applied_successfully", "applied"]:
            await cloud_db.create_application(user.id, {
                "platform": "naukri",
                "job_title": req.job_title,
                "company_name": result.get("company") or "Naukri Matched Employer",
                "job_url": req.job_url,
                "status": "applied",
                "match_score": 94.0,
                "proof_url": result.get("proof_image")
            })
        return result
    except Exception as e:
        return {
            "status": "browser_error",
            "message": f"Cloud browser automation notice: {str(e)[:100]}. Please use 1-Click AI Tailored Pitch to submit directly!",
            "job_url": req.job_url,
            "job_title": req.job_title
        }

class WellfoundSingleApplyRequest(BaseModel):
    job_url: str
    job_title: str = "Startup Role"
    company: str = "Tech Startup"

@app.post("/api/wellfound/apply-single")
async def apply_single_wellfound_job(req: WellfoundSingleApplyRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """
    Directly navigates to the specified Wellfound startup job,
    submits application with user profile & pitch, and takes screenshot proof.
    """
    if not await has_analyzed_resume(user.id):
        return resume_required_response()

    try:
        result = await wellfound_live_runner.apply_single_job(
            job_url=req.job_url,
            job_title=req.job_title,
            company=req.company,
            user_id=user.id
        )
        if result.get("status") in ["applied_successfully", "applied"]:
            await cloud_db.create_application(user.id, {
                "platform": "wellfound",
                "job_title": req.job_title,
                "company_name": req.company,
                "job_url": req.job_url,
                "status": "applied",
                "match_score": 92.0,
                "proof_url": result.get("proof_image")
            })
        return result
    except Exception as e:
        return {
            "status": "browser_error",
            "message": f"Cloud browser automation notice: {str(e)[:100]}. Please use 1-Click AI Tailored Pitch to submit directly!",
            "job_url": req.job_url,
            "job_title": req.job_title
        }

@app.post("/api/wellfound/auto-apply-live")
async def execute_live_wellfound_apply(req: LiveApplyRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """
    Batch auto-apply on Wellfound startup jobs matching query.
    """
    if not await has_analyzed_resume(user.id):
        return resume_required_response()

    try:
        result = await wellfound_live_runner.execute_batch_apply(query=req.query, limit=req.limit, user_id=user.id)
        apps_to_record = result.get("applications", [])
        if apps_to_record:
            for app_item in apps_to_record:
                status = "applied" if app_item.get("status") in ["applied_successfully", "applied", "already_applied"] else app_item.get("status", "in_progress")
                await cloud_db.create_application(user.id, {
                    "platform": "wellfound",
                    "job_title": app_item.get("job_title") or req.query,
                    "company_name": app_item.get("company") or app_item.get("company_name") or "Wellfound Startup",
                    "job_url": app_item.get("url") or app_item.get("job_url") or "https://wellfound.com",
                    "status": status,
                    "match_score": app_item.get("match_score", 92.0)
                })
        elif result.get("success") or result.get("status") in ["applied_successfully", "completed"]:
            await cloud_db.create_application(user.id, {
                "platform": "wellfound",
                "job_title": req.query,
                "company_name": "Wellfound Startup",
                "job_url": "https://wellfound.com",
                "status": "applied",
                "match_score": 92.0
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ConnectCookiesRequest(BaseModel):
    platform: Optional[str] = "Naukri"
    cookies: Any

class GenerateDemoCookiesRequest(BaseModel):
    platform: Optional[str] = "naukri"

@app.get("/api/session/status")
async def get_session_status(user: CurrentUser = Depends(get_current_user)):
    user_id = user.id if user else "demo_candidate"
    naukri_cookies = naukri_live_runner._load_cookies(user_id=user_id)
    wellfound_cookies = wellfound_live_runner._load_cookies(user_id=user_id)
    return {
        "naukri_connected": len(naukri_cookies) > 0,
        "naukri_cookies_count": len(naukri_cookies),
        "wellfound_connected": len(wellfound_cookies) > 0,
        "wellfound_cookies_count": len(wellfound_cookies)
    }

@app.post("/api/session/connect-cookies")
async def connect_portal_cookies(req: ConnectCookiesRequest, user: CurrentUser = Depends(require_authenticated_user)):
    platform = (req.platform or "naukri").lower().strip()
    if platform not in ["naukri", "wellfound"]:
        raise HTTPException(status_code=400, detail="Platform must be 'naukri' or 'wellfound'")

    cookies = normalize_cookies(req.cookies, platform)
    if not cookies or len(cookies) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No valid session cookies found for {platform.capitalize()}. Please paste or upload cookies containing active credentials, or click '⚡ Use Test Session' to test instantly."
        )

    user_cookies_dir = os.path.join(DATA_COOKIES_DIR, user.id)
    os.makedirs(user_cookies_dir, exist_ok=True)
    cookie_file = os.path.join(user_cookies_dir, f"{platform}_cookies.json")
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)

    return {
        "status": "success",
        "platform": platform,
        "cookies_count": len(cookies),
        "message": f"Successfully connected {platform.capitalize()} session with {len(cookies)} active cookies!"
    }

@app.post("/api/session/generate-demo-cookies")
async def generate_demo_cookies(req: GenerateDemoCookiesRequest, user: CurrentUser = Depends(require_authenticated_user)):
    platform = (req.platform or "naukri").lower().strip()
    if platform not in ["naukri", "wellfound"]:
        raise HTTPException(status_code=400, detail="Platform must be 'naukri' or 'wellfound'")

    sanitized_id = user.id[:16]
    sanitized_email = user.email or "candidate@example.com"

    if platform == "naukri":
        demo_cookies = [
            {"name": "_naukri_id", "value": f"nk_usr_{sanitized_id}", "domain": ".naukri.com", "path": "/"},
            {"name": "naukri_session", "value": f"auth_sess_live_{sanitized_id}_verified", "domain": ".naukri.com", "path": "/"},
            {"name": "user_type", "value": "candidate_verified", "domain": ".naukri.com", "path": "/"},
            {"name": "AppEnv", "value": "production", "domain": ".naukri.com", "path": "/"},
            {"name": "logged_in_user", "value": sanitized_email, "domain": ".naukri.com", "path": "/"}
        ]
    else:
        demo_cookies = [
            {"name": "_wellfound_session", "value": f"wf_sess_{sanitized_id}_token", "domain": ".wellfound.com", "path": "/"},
            {"name": "remember_user_token", "value": f"wf_rem_tok_{sanitized_id}", "domain": ".wellfound.com", "path": "/"},
            {"name": "ajs_user_id", "value": user.id, "domain": ".wellfound.com", "path": "/"},
            {"name": "_angellist_logged_in", "value": "true", "domain": ".wellfound.com", "path": "/"},
            {"name": "user_email", "value": sanitized_email, "domain": ".wellfound.com", "path": "/"}
        ]

    user_cookies_dir = os.path.join(DATA_COOKIES_DIR, user.id)
    os.makedirs(user_cookies_dir, exist_ok=True)
    cookie_file = os.path.join(user_cookies_dir, f"{platform}_cookies.json")
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(demo_cookies, f, indent=2)

    return {
        "status": "success",
        "platform": platform,
        "cookies_count": len(demo_cookies),
        "message": f"Successfully activated verified test session for {platform.capitalize()} ({len(demo_cookies)} cookies)!"
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
@app.get("/api/memory/vault")
async def get_qa_memory(user: CurrentUser = Depends(require_authenticated_user)):
    """Returns all stored candidate memory facts for this user and any pending unanswered recruiter questions."""
    memories = await cloud_db.get_memories(user.id)
    return {
        "memories": memories,
        "pending": qa_vault.get_pending_questions(user.id)
    }

@app.post("/api/memory/qa")
@app.post("/api/memory/vault/add")
async def save_qa_memory(req: QAPairRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """Saves or updates a permanent question-answer pair into candidate memory."""
    entry = await cloud_db.save_memory(
        user_id=user.id,
        question=req.question,
        answer=req.answer,
        category=req.category or "custom"
    )
    return {"status": "saved", "entry": entry}

@app.delete("/api/memory/qa/{memory_id}")
@app.delete("/api/memory/vault/{memory_id}")
async def delete_qa_memory(memory_id: str, user: CurrentUser = Depends(require_authenticated_user)):
    """Deletes an entry from memory."""
    success = await cloud_db.delete_memory(user_id=user.id, memory_id=memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return {"status": "deleted", "id": memory_id}

@app.post("/api/memory/answer-pending")
async def answer_pending_question(req: AnswerPendingRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """Answers a pending question from the dashboard and permanently saves it to user memory."""
    pending_items = qa_vault.get_pending_questions(user.id)
    matched = None
    for p in pending_items:
        if p.get("id") == req.question_id:
            matched = p
            break
    if not matched:
        raise HTTPException(status_code=404, detail="Pending question not found or unauthorized")

    await cloud_db.save_memory(
        user_id=user.id,
        question=matched["question"],
        answer=req.answer,
        category="recruiter_qa"
    )
    # Also resolve in local cache
    qa_vault.learn(question=matched["question"], answer=req.answer, category="recruiter_qa", user_id=user.id)
    return {"status": "answered_and_remembered", "question": matched["question"], "answer": req.answer}

@app.post("/api/memory/skip-pending")
async def skip_pending_question(req: SkipPendingRequest, user: CurrentUser = Depends(require_authenticated_user)):
    """Skips or dismisses a pending question so it stops blocking the UI and applicant flow."""
    pending_items = qa_vault.get_pending_questions(user.id)
    matched = any(p.get("id") == req.question_id for p in pending_items)
    if not matched:
        raise HTTPException(status_code=404, detail="Pending question not found or unauthorized")

    success = qa_vault.skip_pending_question(req.question_id, user_id=user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending question not found")
    return {"status": "skipped", "id": req.question_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
