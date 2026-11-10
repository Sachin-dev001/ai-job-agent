import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_COOKIES_DIR = BACKEND_DIR / "data" / "cookies"
DATA_COOKIES_DIR.mkdir(parents=True, exist_ok=True)

class NaukriApplyAgent:
    """
    Submits applications to Naukri using your authenticated session.
    - Multi-tenant cookie isolation partitioned strictly by user_id.
    - Verifies user authentication before processing.
    - Executes real DOM submission via Naukri live runner.
    - NEVER returns simulated or fake 'applied_successfully' without live DOM confirmation!
    """
    def __init__(self):
        pass

    def _load_cookies(self, user_id: str = None):
        from app.agents.naukri_live_runner import naukri_live_runner
        return naukri_live_runner._load_cookies(user_id=user_id)

    async def apply_to_job(self, job_title: str, company: str, job_url: str, user_id: str = None) -> Dict[str, Any]:
        """
        Submits a real application to a live Naukri job listing.
        Strict verification: Only returns applied_successfully if verified on live DOM.
        """
        cookies = self._load_cookies(user_id=user_id)
        if not cookies:
            return {
                "status": "session_required",
                "message": "No active session cookies connected for your account. Please connect your cookies in Settings or export from your logged-in Naukri browser."
            }

        from app.agents.naukri_live_runner import naukri_live_runner
        # Verify active session authentication
        is_valid, session_msg = await naukri_live_runner.verify_naukri_session(cookies)
        if not is_valid:
            return {
                "status": "session_expired",
                "message": session_msg or "Your Naukri session has expired or is invalid. Please reconnect active cookies in Settings."
            }

        # Delegate strictly to real live runner for DOM execution & verification
        print(f"[Naukri Apply Agent] Delegating application to live runner: {job_title} @ {company}")
        res = await naukri_live_runner.apply_single_job(
            job_url=job_url,
            job_title=job_title,
            company=company,
            user_id=user_id
        )
        return res

naukri_apply_agent = NaukriApplyAgent()
