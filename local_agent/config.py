import os
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_AGENT_DIR = ROOT_DIR / "local_agent"
PROFILE_PATH = LOCAL_AGENT_DIR / "candidate_profile.json"
BROWSER_PROFILE_DIR = ROOT_DIR / "local_browser_profile"
PROOFS_DIR = ROOT_DIR / "proofs"
PROOFS_DIR.mkdir(parents=True, exist_ok=True)
BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Default to headed mode so the user can visually witness every application live
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("true", "1")

def get_candidate_profile() -> dict:
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Error reading candidate profile: {e}")
    return {
        "full_name": "Sachin Sharma",
        "first_name": "Sachin",
        "last_name": "Sharma",
        "email": "sachin.sharma.engineer@gmail.com",
        "phone": "+91 9876543210",
        "total_experience_years": 3.5,
        "notice_period_days": 15,
        "notice_period_str": "15 Days or less",
        "current_ctc_lakhs": 12,
        "expected_ctc_lakhs": 18,
        "highest_qualification": "B.Tech in Computer Science",
        "skills": ["Python", "FastAPI", "Generative AI", "LLMs", "LangChain", "Docker"],
        "resume_path": "sample_resume.pdf"
    }

def get_resume_path() -> Path:
    profile = get_candidate_profile()
    resume_file = profile.get("resume_path", "sample_resume.pdf")
    path = ROOT_DIR / resume_file
    if not path.exists():
        # Fallback to any sample resume
        sample_path = ROOT_DIR / "sample_resume.pdf"
        if sample_path.exists():
            return sample_path
    return path
