import os
import sys
import json
import asyncio
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from local_agent.config import (
    ROOT_DIR, LOCAL_AGENT_DIR, PROFILE_PATH, BROWSER_PROFILE_DIR, PROOFS_DIR,
    get_candidate_profile, get_resume_path, HEADLESS
)
from local_agent.browser_manager import LocalBrowserManager
from local_agent.naukri_applier import LocalNaukriApplier
from local_agent.wellfound_applier import LocalWellfoundApplier
from local_agent.job_scout import LocalJobScout
from local_agent.session_setup import run_session_setup

app = FastAPI(title="Local Autonomous Job Agent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static proofs serving
app.mount("/proofs", StaticFiles(directory=str(PROOFS_DIR)), name="proofs")

# Global event queue for live UI logs
log_subscribers: List[asyncio.Queue] = []

async def broadcast_log(level: str, message: str, meta: Optional[dict] = None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    payload = {
        "time": timestamp,
        "level": level,
        "message": message,
        "meta": meta or {}
    }
    raw = f"data: {json.dumps(payload)}\n\n"
    for q in list(log_subscribers):
        try:
            await q.put(raw)
        except Exception:
            pass

# UI HTML Path
UI_FILE = LOCAL_AGENT_DIR / "ui" / "index.html"

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    if UI_FILE.exists():
        with open(UI_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Local Job Agent UI Initializing...</h1>")

@app.get("/api/logs/stream")
async def stream_logs():
    q = asyncio.Queue()
    log_subscribers.append(q)

    async def event_generator():
        try:
            # Send initial welcome log
            await q.put(f"data: {json.dumps({'time': datetime.now().strftime('%H:%M:%S'), 'level': 'info', 'message': '⚡ Connected to Local Job Agent Server'})}\n\n")
            while True:
                data = await q.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            if q in log_subscribers:
                log_subscribers.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/status")
async def get_system_status():
    naukri_logged_in = False
    wellfound_logged_in = False
    naukri_cookies_count = 0
    wellfound_cookies_count = 0

    try:
        async with LocalBrowserManager(headless=True) as bm:
            cookies = await bm.context.cookies()
            nc = [c['name'] for c in cookies if 'naukri' in c.get('domain', '')]
            wc = [c['name'] for c in cookies if 'wellfound' in c.get('domain', '') or 'angel' in c.get('domain', '')]
            naukri_cookies_count = len(nc)
            wellfound_cookies_count = len(wc)
            naukri_logged_in = len(nc) >= 5
            wellfound_logged_in = len(wc) >= 2
    except Exception as e:
        print(f"[Status Error] {e}")

    profile = get_candidate_profile()
    resume_file = get_resume_path()
    
    proof_files = list(PROOFS_DIR.glob("*.png"))

    return {
        "naukri_connected": naukri_logged_in,
        "naukri_cookies_count": naukri_cookies_count,
        "wellfound_connected": wellfound_logged_in,
        "wellfound_cookies_count": wellfound_cookies_count,
        "candidate_name": profile.get("full_name", "Sachin Sharma"),
        "active_resume": resume_file.name if resume_file.exists() else "None",
        "proofs_count": len(proof_files),
        "engine": "Playwright + Chromium (Residential IP)"
    }

class LaunchSessionRequest(BaseModel):
    pass

@app.post("/api/setup-session")
async def launch_session_setup_bg(background_tasks: BackgroundTasks):
    await broadcast_log("info", "🔑 Opening Google Chrome window to log into Naukri & Wellfound...")
    
    async def _setup_task():
        try:
            async with LocalBrowserManager(headless=False) as bm:
                page = await bm.get_page()
                await page.goto("https://www.naukri.com/nlogin/login")
                page2 = await bm.new_stealth_page()
                await page2.goto("https://wellfound.com/login")
                
                await broadcast_log("info", "👉 Please log into Naukri and Wellfound in the opened Chrome window. Keep the browser open until you finish.")
                # Give user time to log in
                for i in range(120): # up to 4 minutes
                    await asyncio.sleep(2)
                    if len(bm.context.pages) == 0:
                        break
                
                # Check status
                cookies = await bm.context.cookies()
                nc = [c['name'] for c in cookies if 'naukri' in c.get('domain', '')]
                wc = [c['name'] for c in cookies if 'wellfound' in c.get('domain', '') or 'angel' in c.get('domain', '')]
                await broadcast_log("success", f"🎉 Session saved permanently! Naukri: {len(nc)} cookies, Wellfound: {len(wc)} cookies.")
        except Exception as e:
            await broadcast_log("error", f"Session setup error: {e}")

    background_tasks.add_task(_setup_task)
    return {"status": "launched", "message": "Chrome window launched for 1-time login."}

class ApplyRequest(BaseModel):
    url: str
    headless: Optional[bool] = False

@app.post("/api/apply")
async def execute_apply(req: ApplyRequest):
    url = req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid job URL. Must start with http:// or https://")

    portal = "Naukri" if "naukri.com" in url else ("Wellfound" if "wellfound.com" in url else "Unknown")
    await broadcast_log("info", f"🚀 Starting auto-apply for {portal} job: {url}")
    await broadcast_log("info", f"🖥️ Launching browser ({'Headless' if req.headless else 'Headed mode - visible on screen'})...")

    try:
        async with LocalBrowserManager(headless=req.headless) as bm:
            page = await bm.get_page()
            
            if "naukri.com" in url:
                await broadcast_log("info", "🌐 Navigating to Naukri job listing...")
                applier = LocalNaukriApplier(page)
                res = await applier.apply_to_job(url)
            elif "wellfound.com" in url:
                await broadcast_log("info", "🌐 Navigating to Wellfound job listing...")
                applier = LocalWellfoundApplier(page)
                res = await applier.apply_to_job(url)
            else:
                await broadcast_log("error", f"Unsupported job portal: {url}")
                return {"status": "error", "message": "Only Naukri.com and Wellfound.com job URLs are supported."}

            proof_filename = os.path.basename(res.get("proof_path", ""))
            proof_url = f"/proofs/{proof_filename}" if proof_filename else None

            if res.get("status") == "applied_successfully":
                await broadcast_log("success", f"🎉 100% VERIFIED: Application submitted to '{res.get('company')}' for role '{res.get('job_title')}'!", {"proof_url": proof_url})
            else:
                await broadcast_log("warn", f"Notice: {res.get('message')}", {"proof_url": proof_url})

            return {
                **res,
                "proof_url": proof_url
            }
    except Exception as e:
        await broadcast_log("error", f"Application exception: {e}")
        return {"status": "error", "message": str(e)}

class ScoutRequest(BaseModel):
    keyword: Optional[str] = "Python Developer"
    location: Optional[str] = "Bengaluru"
    limit: Optional[int] = 5

@app.post("/api/scout")
async def scout_jobs(req: ScoutRequest):
    await broadcast_log("info", f"🔍 Scouting jobs for '{req.keyword}' in '{req.location}'...")
    try:
        async with LocalBrowserManager(headless=True) as bm:
            page = await bm.get_page()
            scout = LocalJobScout(page)
            naukri_jobs = await scout.scout_naukri(keyword=req.keyword, location=req.location, limit=req.limit)
            
            await broadcast_log("success", f"Found {len(naukri_jobs)} matching jobs!")
            return {"jobs": naukri_jobs}
    except Exception as e:
        await broadcast_log("error", f"Scout error: {e}")
        return {"jobs": [], "error": str(e)}

@app.get("/api/profile")
async def get_profile():
    return get_candidate_profile()

@app.post("/api/profile")
async def save_profile(data: dict):
    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        await broadcast_log("success", "Candidate profile updated successfully.")
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    dest = ROOT_DIR / file.filename
    with open(dest, "wb") as buffer:
        buffer.write(await file.read())
    
    # Update profile resume_path
    profile = get_candidate_profile()
    profile["resume_path"] = file.filename
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    await broadcast_log("success", f"📄 Resume uploaded and activated: {file.filename}")
    return {"status": "uploaded", "filename": file.filename}

@app.get("/api/proofs")
async def list_proofs():
    files = sorted(PROOFS_DIR.glob("*.png"), key=os.path.getmtime, reverse=True)
    proofs = []
    for f in files:
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M:%S")
        portal = "Naukri" if "naukri" in f.name.lower() else ("Wellfound" if "wellfound" in f.name.lower() else "Portal")
        proofs.append({
            "filename": f.name,
            "url": f"/proofs/{f.name}",
            "portal": portal,
            "timestamp": mtime,
            "size_kb": round(f.stat().st_size / 1024, 1)
        })
    return {"proofs": proofs}

def start_server():
    import uvicorn
    # Open browser on start
    def _open():
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:8000")

    asyncio.get_event_loop().run_in_executor(None, _open)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    start_server()
