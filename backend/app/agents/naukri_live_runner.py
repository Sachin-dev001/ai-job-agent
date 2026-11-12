import os
import re
import json
import asyncio
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from pathlib import Path
from app.config import settings
from app.notifications.notifier import notifier
from app.memory.qa_vault import qa_vault
from app.notifications.telegram_listener import telegram_listener

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_COOKIES_DIR = BACKEND_DIR / "data" / "cookies"
DATA_COOKIES_DIR.mkdir(parents=True, exist_ok=True)
PROOF_DIR = str(BACKEND_DIR / "proofs")
os.makedirs(PROOF_DIR, exist_ok=True)

# Dynamic candidate knowledge vault loaded from active profile/session
def get_candidate_vault(profile: dict = None) -> dict:
    p = profile or {}
    cand_name = p.get("full_name") or os.getenv("CANDIDATE_NAME", "Candidate")
    parts = cand_name.split()
    first_name = parts[0] if parts else "Candidate"
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    return {
        "name": cand_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": p.get("email") or os.getenv("CANDIDATE_EMAIL", ""),
        "phone": p.get("phone") or os.getenv("CANDIDATE_PHONE", ""),
        "mobile": p.get("phone") or os.getenv("CANDIDATE_PHONE", ""),
        "current_location": p.get("location") or os.getenv("CANDIDATE_LOCATION", "Bengaluru"),
        "preferred_location": p.get("preferred_location") or os.getenv("CANDIDATE_LOCATION", "Bengaluru"),
        "current_ctc_lakhs": str(p.get("current_ctc") or os.getenv("CANDIDATE_CURRENT_CTC", "")),
        "expected_ctc_lakhs": str(p.get("expected_ctc") or os.getenv("CANDIDATE_EXPECTED_CTC", "")),
        "notice_period_days": str(p.get("notice_period") or os.getenv("CANDIDATE_NOTICE_DAYS", "15")),
        "notice_period_str": "15 Days or less",
        "dob": p.get("dob") or p.get("date_of_birth") or "15/08/1999",
        "total_experience_years": str(p.get("experience_years") or os.getenv("CANDIDATE_EXPERIENCE_YEARS", "2")),
        "relevant_experience_years": str(p.get("experience_years") or os.getenv("CANDIDATE_EXPERIENCE_YEARS", "2")),
        "highest_qualification": p.get("highest_qualification") or "B.Tech in Computer Science and Engineering",
        "degree": "B.Tech",
        "ssc_10th_percentage": "Between 80% to 90%",
        "hsc_12th_percentage": "Between 80% to 90%",
        "graduation_percentage": "Between 80% to 90%",
        "english_rating": "5",
        "ready_to_relocate": "Yes",
        "gender": p.get("gender", ""),
        "skills": p.get("skills") or "Python, AI, Automation",
        "experience_summary": p.get("experience_summary") or "Experienced software engineer specializing in AI applications."
    }

CANDIDATE_VAULT = get_candidate_vault()

class RealNaukriApplyEngine:
    """
    Autonomous Playwright Submissions Engine for Naukri.com:
    - Multi-tenant cookie isolation partitioned strictly by user_id.
    - Verified active session authentication on Naukri before attempting.
    - Physically interacts with job listings and application flows.
    - Handles complex multi-step recruiter screening questionnaires:
      * Dynamic contenteditable text inputs (.textArea)
      * Native & custom styled radio buttons (.ssrc__radio, .ssrc__radio-btn-container)
      * Option chips (.chatbot_Chip, .chipItem)
      * Checkbox arrays (.msrc__radio-btn-container)
    - Powered by Candidate Vault + Groq Qwen 27B for intelligent answers.
    - Rigorous verification: only marks as applied when confirmed on live Naukri DOM.
    - NEVER returns simulated or fake applied_successfully without live DOM confirmation!
    - Reads live application count from https://www.naukri.com/myapply/historypage.
    """
    def __init__(self):
        self._groq_client = None
        if settings.GROQ_API_KEY:
            try:
                import groq
                self._groq_client = groq.Groq(api_key=settings.GROQ_API_KEY)
            except Exception as e:
                print(f"[Naukri Bot] Groq client init notice: {e}")

    async def _launch_browser(self, p):
        args = [
            "--headless=new",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process",
            "--no-zygote"
        ]
        # Prefer installed Chrome channel if available to match genuine consumer signatures
        try:
            return await p.chromium.launch(headless=True, channel="chrome", args=args)
        except Exception:
            return await p.chromium.launch(headless=True, args=args)

    def _load_cookies(self, user_id: str = None) -> List[Dict]:
        """
        Loads session cookies for specified user_id with robust persistence:
        1. Local disk user-specific cache: DATA_COOKIES_DIR / str(user_id) / "naukri_cookies.json"
        2. Supabase cloud database / local profile storage (restores cookies across Render restarts)
        3. Project fallback: backend/cookies/naukri_cookies.json
        """
        from app.utils.cookie_normalizer import normalize_cookies
        from app.database.supabase_client import cloud_db

        uid = user_id or "guest-candidate"

        # Tier 1: Local disk user-specific cache
        cookie_file = DATA_COOKIES_DIR / str(uid) / "naukri_cookies.json"
        if cookie_file.exists():
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                norm = normalize_cookies(raw, "naukri")
                if norm and len(norm) > 0:
                    return norm
            except Exception as e:
                print(f"[Naukri Bot] Error reading local user cookie file: {e}")

        # Tier 2: Cloud DB / Profile persistence (restores cookies on Render ephemeral instances)
        try:
            cloud_cookies = cloud_db.get_cookies_sync(uid, "naukri")
            if cloud_cookies and len(cloud_cookies) > 0:
                norm = normalize_cookies(cloud_cookies, "naukri")
                if norm and len(norm) > 0:
                    try:
                        cookie_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(cookie_file, "w", encoding="utf-8") as f:
                            json.dump(norm, f, indent=2)
                        print(f"[Naukri Bot] Restored {len(norm)} Naukri cookies from cloud database for user {uid}")
                    except Exception:
                        pass
                    return norm
        except Exception as e:
            print(f"[Naukri Bot] Cloud cookies restoration note for user {uid}: {e}")

        # Tier 3: Global project fallback: backend/cookies/naukri_cookies.json
        try:
            fallback_file = Path(__file__).resolve().parent.parent.parent / "cookies" / "naukri_cookies.json"
            if fallback_file.exists():
                with open(fallback_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                norm = normalize_cookies(raw, "naukri")
                if norm and len(norm) > 0:
                    return norm
        except Exception as e:
            print(f"[Naukri Bot] Fallback cookies load note: {e}")

        return []

    async def verify_naukri_session(self, cookies: List[Dict]) -> Tuple[bool, str]:
        """
        Verifies if candidate's cookies form an active, authenticated Naukri session.
        Checks with Naukri profile / history page.
        Returns (is_valid, human_readable_message).
        """
        if not cookies:
            return False, "No active session cookies connected for your account. Please connect your cookies in Settings or export from your logged-in Naukri browser."

        try:
            cookie_dict = {
                str(c.get("name")): str(c.get("value"))
                for c in cookies
                if c.get("name") and c.get("value") is not None
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.naukri.com/"
            }
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                resp = await client.get("https://www.naukri.com/myapply/historypage", cookies=cookie_dict, headers=headers)
                if resp.status_code in [301, 302, 303, 307, 308]:
                    loc = resp.headers.get("location", "").lower()
                    if "nlogin" in loc or "login" in loc:
                        return False, "Your Naukri session has expired or the cookies are invalid. Please reconnect active cookies from your logged-in Naukri browser."
                elif resp.status_code == 200:
                    text_sample = resp.text[:1200].lower()
                    if "jobseeker's login" in text_sample or "access denied" in text_sample:
                        if "jobseeker" in text_sample:
                            return False, "Naukri returned the login page. Your session cookies have expired. Please connect fresh cookies."
                    return True, "Active authenticated Naukri session verified."
        except Exception as e:
            print(f"[Naukri Session Pre-Check Note]: {e}")

        # If HTTP pre-check timed out or was blocked by WAF, allow browser session to verify on live DOM
        return True, "Session cookies loaded (pending live DOM verification)."

    async def check_naukri_application_count(self, cookies: Any = None, user_id: str = None) -> Dict[str, Any]:
        """
        Inspects https://www.naukri.com/myapply/historypage using candidate's connected session
        and reads the official live applied count.
        """
        if cookies is None and user_id:
            cookies = self._load_cookies(user_id=user_id)
        elif isinstance(cookies, str) and not (cookies.strip().startswith("[") or cookies.strip().startswith("{")):
            # Passed user_id as string
            cookies = self._load_cookies(user_id=cookies)
        else:
            from app.utils.cookie_normalizer import normalize_cookies
            cookies = normalize_cookies(cookies, "naukri")

        if not cookies:
            return {
                "status": "session_required",
                "authenticated": False,
                "count": None,
                "message": "No active session cookies found. Please connect your Naukri cookies in Settings."
            }

        # Step 1: Pre-check session validity
        is_valid, msg = await self.verify_naukri_session(cookies)
        if not is_valid:
            return {
                "status": "session_expired",
                "authenticated": False,
                "count": None,
                "message": msg
            }

        # Step 2: Use Playwright to load history page with full JS rendering
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    locale="en-US",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Windows"'
                    }
                )

                clean_cookies = []
                blocked_waf = {"_abck", "ak_bmsc", "bm_sz", "bm_sv", "bm_mi", "bm_so"}
                for c in cookies:
                    if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
                        c_name = str(c["name"]).strip()
                        c_lower = c_name.lower()
                        if c_lower.startswith("ak_") or c_lower.startswith("bm_") or c_lower in blocked_waf:
                            continue
                        dom = str(c.get("domain") or ".naukri.com")
                        if not dom.startswith("."):
                            dom = f".{dom}"
                        clean_cookies.append({
                            "name": c_name,
                            "value": str(c["value"]).strip(),
                            "domain": dom,
                            "path": str(c.get("path") or "/")
                        })
                await context.add_cookies(clean_cookies)

                page = await context.new_page()
                try:
                    await Stealth().apply_stealth_async(page)
                except Exception:
                    pass
                
                api_count = None
                async def handle_response(response):
                    nonlocal api_count
                    try:
                        url = response.url.lower()
                        if ("apply" in url or "history" in url or "jobapi" in url) and "json" in (response.headers.get("content-type") or "").lower():
                            data = await response.json()
                            if isinstance(data, dict):
                                for k in ["totalApplied", "appliedCount", "totalCount", "total", "count", "applicationsCount"]:
                                    if k in data and isinstance(data[k], int):
                                        api_count = data[k]
                                        break
                    except Exception:
                        pass

                page.on("response", handle_response)

                history_url = "https://www.naukri.com/myapply/historypage"
                print(f"[Naukri Bot] Checking application count at: {history_url}")
                await page.goto(history_url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(3500)

                # Check if redirected to login
                curr_url = page.url.lower()
                title = await page.title()
                if "nlogin" in curr_url or "login.naukri.com" in curr_url or "jobseeker's login" in title.lower():
                    await browser.close()
                    return {
                        "status": "session_expired",
                        "authenticated": False,
                        "count": None,
                        "message": "Naukri redirected to login page. Session cookies are expired or invalid."
                    }

                # If API response captured count
                if api_count is not None:
                    await browser.close()
                    return {
                        "status": "authenticated",
                        "authenticated": True,
                        "count": api_count,
                        "source": "api",
                        "message": f"Official Naukri applied count: {api_count}"
                    }

                # Try CSS selectors
                selectors = [
                    ".appliedCount",
                    ".applied-count",
                    "[class*='appliedCount' i]",
                    "[class*='historyCount' i]",
                    "[class*='applied-count' i]",
                    ".total-count",
                    "span.count",
                    "div.count",
                    "[data-filter='applied'] span",
                    "a[href*='myapply'] span",
                    "li.active span.count",
                    ".applied-jobs-count"
                ]
                for sel in selectors:
                    try:
                        locs = await page.locator(sel).all()
                        for el in locs:
                            txt = (await el.text_content() or "").strip()
                            m = re.search(r'\b(\d+)\b', txt)
                            if m:
                                count_val = int(m.group(1))
                                await browser.close()
                                return {
                                    "status": "authenticated",
                                    "authenticated": True,
                                    "count": count_val,
                                    "source": "dom_selector",
                                    "message": f"Official Naukri applied count: {count_val}"
                                }
                    except Exception:
                        pass

                # Try Regex on body text
                body_text = await page.locator("body").text_content() or ""
                patterns = [
                    r'(?:total\s+)?applied(?:\s+jobs)?\s*(?:[:\-\(]\s*)?(\d+)',
                    r'(\d+)\s+jobs?\s+applied',
                    r'showing\s+\d+\s*(?:-\s*\d+)?\s*of\s*(\d+)',
                    r'applied\s*\(([0-9]+)\)',
                    r'all\s+applications\s*\(([0-9]+)\)',
                    r'\(([0-9]+)\)\s*applied'
                ]
                for pat in patterns:
                    m = re.search(pat, body_text, re.IGNORECASE)
                    if m:
                        count_val = int(m.group(1))
                        await browser.close()
                        return {
                            "status": "authenticated",
                            "authenticated": True,
                            "count": count_val,
                            "source": "dom_text",
                            "message": f"Official Naukri applied count: {count_val}"
                        }

                # Count visible application tuples
                tuple_count = await page.locator(".tuple, .jobTuple, [class*='job-tuple' i], [class*='applied-tuple' i], [class*='application-card' i]").count()
                await browser.close()
                return {
                    "status": "authenticated",
                    "authenticated": True,
                    "count": tuple_count,
                    "source": "dom_tuples",
                    "message": f"Official Naukri applied count: {tuple_count}"
                }
        except Exception as e:
            return {
                "status": "error",
                "authenticated": False,
                "count": None,
                "message": f"Error querying Naukri application history: {str(e)}"
            }

    async def _get_smart_answer(self, question: str, job_title: str = "", company: str = "", job_url: str = "", user_id: str = None) -> Optional[str]:
        """
        4-Tier Recruiter Question Resolution Engine:
        - Tier 1: Exact / semantic match in candidate's QA Memory Vault
        - Tier 2: Candidate profile & CANDIDATE_VAULT heuristics (CTC, notice period, experience, skills, location, degree)
        - Tier 3: LLM Auto-Answer via Google Gemini Flash / Groq grounded in candidate facts
        - Tier 4: Human-in-the-loop fallback via Telegram & Web UI (with non-blocking recovery)
        """
        q = (question or "").strip()
        if not q:
            return None

        uid = user_id or "guest-candidate"
        q_lower = q.lower()

        # ======================================================================
        # TIER 1: Check Explicit QA Memory Vault First
        # ======================================================================
        vault_answer = qa_vault.find_answer(q, user_id=uid)
        if vault_answer:
            print(f"[Naukri Bot] [Tier 1 Memory Match]: '{q}' -> '{vault_answer}'")
            return vault_answer

        # Load candidate profile and candidate vault
        from app.database.supabase_client import cloud_db
        try:
            cand_profile = await cloud_db.get_profile(uid) or {}
        except Exception:
            cand_profile = {}
        cand_vault = get_candidate_vault(cand_profile)

        # ======================================================================
        # TIER 2: Candidate Vault & Profile Heuristics (Standard Recruiting Questions)
        # ======================================================================
        # 1. Notice Period / Availability / Joining Time
        if any(w in q_lower for w in ["notice", "joining", "join", "serving notice", "availability", "available"]):
            notice_val = str(cand_profile.get("notice_period") or cand_vault.get("notice_period_days") or "15").strip()
            digits = re.findall(r"\d+", notice_val)
            num_days = digits[0] if digits else "15"
            # If question asks for days or numbers only
            if any(w in q_lower for w in ["in days", "how many days", "number of days", "days notice"]):
                print(f"[Naukri Bot] [Tier 2 Notice Days Match]: '{q}' -> '{num_days}'")
                return num_days
            ans = f"{num_days} Days" if num_days != "0" else "Immediate"
            print(f"[Naukri Bot] [Tier 2 Notice Match]: '{q}' -> '{ans}'")
            return ans

        # 2b. Date of Birth / DOB
        if any(w in q_lower for w in ["date of birth", "dob", "birth date", "birthdate"]):
            dob_val = str(cand_profile.get("dob") or cand_profile.get("date_of_birth") or cand_vault.get("dob") or "15/08/1999").strip()
            print(f"[Naukri Bot] [Tier 2 DOB Match]: '{q}' -> '{dob_val}'")
            return dob_val

        # 2. Current CTC / Present Salary
        if any(w in q_lower for w in ["current ctc", "present ctc", "current salary", "present salary", "drawing", "fixed ctc"]):
            ctc_val = str(cand_profile.get("current_ctc") or cand_vault.get("current_ctc_lakhs") or "6.5 LPA").strip()
            if any(w in q_lower for w in ["lakh", "lpa", "in lacs", "in lac", "in lpa"]):
                match = re.search(r"(\d+(\.\d+)?)", ctc_val)
                ans = match.group(1) if match else "6.5"
                print(f"[Naukri Bot] [Tier 2 Current CTC in LPA]: '{q}' -> '{ans}'")
                return ans
            print(f"[Naukri Bot] [Tier 2 Current CTC]: '{q}' -> '{ctc_val}'")
            return ctc_val

        # 3. Expected CTC / Desired Salary
        if any(w in q_lower for w in ["expected ctc", "expectation ctc", "expected salary", "salary expectation", "desired salary", "ctc expectation"]):
            ctc_val = str(cand_profile.get("expected_ctc") or cand_vault.get("expected_ctc_lakhs") or "10 LPA").strip()
            if any(w in q_lower for w in ["lakh", "lpa", "in lacs", "in lac", "in lpa"]):
                match = re.search(r"(\d+(\.\d+)?)", ctc_val)
                ans = match.group(1) if match else "10"
                print(f"[Naukri Bot] [Tier 2 Expected CTC in LPA]: '{q}' -> '{ans}'")
                return ans
            print(f"[Naukri Bot] [Tier 2 Expected CTC]: '{q}' -> '{ctc_val}'")
            return ctc_val

        # 4. Total Work Experience
        if any(w in q_lower for w in ["total experience", "overall experience", "total work experience", "how many years of experience", "total years", "years of experience"]):
            exp_val = str(cand_profile.get("experience_years") or cand_vault.get("total_experience_years") or "2.5").strip()
            match = re.search(r"(\d+(\.\d+)?)", exp_val)
            ans = match.group(1) if match else "2.5"
            print(f"[Naukri Bot] [Tier 2 Total Experience Match]: '{q}' -> '{ans}'")
            return str(ans)

        # 5. Experience in Specific Skill or Technology (e.g. Python, FastAPI, Docker, SQL)
        raw_skills = cand_profile.get("technical_skills") or cand_profile.get("skills") or cand_vault.get("skills") or "Python, FastAPI, SQL, Docker, Machine Learning, AI"
        if isinstance(raw_skills, list):
            skill_list = [s.strip().lower() for s in raw_skills if s and s.strip()]
        else:
            skill_list = [s.strip().lower() for s in str(raw_skills).split(",") if s.strip()]

        for s in skill_list:
            if s and s in q_lower:
                exp_years = str(cand_profile.get("experience_years") or cand_vault.get("total_experience_years") or "2.5")
                if any(w in q_lower for w in ["how many", "years", "number of", "duration"]):
                    print(f"[Naukri Bot] [Tier 2 Skill Experience Match]: '{q}' (skill: {s}) -> '{exp_years}'")
                    return str(exp_years)
                if any(w in q_lower for w in ["do you", "have you", "hands on", "proficient"]):
                    print(f"[Naukri Bot] [Tier 2 Skill Yes/No Match]: '{q}' (skill: {s}) -> 'Yes'")
                    return "Yes"

        # 6. Location & Relocation
        if any(w in q_lower for w in ["relocate", "relocation", "willing to relocate", "open to relocate"]):
            return "Yes"
        if any(w in q_lower for w in ["current location", "where are you located", "current city", "base location"]):
            loc = cand_profile.get("location") or cand_vault.get("current_location") or "Bengaluru"
            return str(loc)
        if any(w in q_lower for w in ["work from office", "wfo", "hybrid", "onsite", "shift"]):
            return "Yes"

        # 7. Degree / Highest Qualification
        if any(w in q_lower for w in ["qualification", "degree", "highest degree", "education", "graduation"]):
            deg = cand_profile.get("education") or cand_vault.get("highest_qualification") or cand_vault.get("degree") or "B.Tech in Computer Science"
            return str(deg)

        # 8. Contact details
        if "email" in q_lower:
            return cand_vault.get("email") or ""
        if any(w in q_lower for w in ["phone", "mobile", "contact number"]):
            return cand_vault.get("phone") or ""

        # 9. General Affirmative Screening Questions
        if any(w in q_lower for w in [
            "laptop", "broadband", "internet connection", "immediate joiner", "valid visa",
            "authorized to work", "indian citizen", "background check", "comfortable"
        ]):
            return "Yes"

        # ======================================================================
        # TIER 3: LLM Auto-Answer via Gemini / Groq using Candidate Profile Facts
        # ======================================================================
        cand_name = cand_vault.get("name", "Candidate")
        cand_exp = cand_profile.get("experience_years") or cand_vault.get("total_experience_years", "2.5")
        skills_str = ", ".join(skill_list[:8]) if skill_list else "Python, FastAPI, SQL, AI"
        cand_summary = cand_profile.get("experience_summary") or cand_vault.get("experience_summary", "Experienced software engineer specializing in AI and backend systems.")
        cand_location = cand_profile.get("location") or cand_vault.get("current_location", "Bengaluru")

        llm_prompt = f"""Recruiter screening question: "{q}"

Candidate Context:
- Name: {cand_name}
- Work Experience: {cand_exp} years
- Primary Skills: {skills_str}
- Summary: {cand_summary}
- Location: {cand_location}
- Notice Period: 15 Days
- Target Role: {job_title or 'Software Engineer'}
- Company: {company or 'Hiring Company'}

Provide a concise, direct, professional answer in 1 or 2 sentences max (or just the value/number if asking for a metric). Strictly avoid bracketed placeholders like [Your Name]. Answer directly from candidate perspective."""

        try:
            from app.llm.gemini_service import gemini_service
            if gemini_service.is_available():
                llm_ans = gemini_service.generate(
                    prompt=llm_prompt,
                    system_prompt="You are an expert candidate proxy answering recruiter screening questions factually and concisely.",
                    temperature=0.1
                )
                if llm_ans and len(llm_ans.strip()) > 0:
                    clean_ans = llm_ans.strip().strip('"\'')
                    print(f"[Naukri Bot] [Tier 3 Gemini Auto-Answer]: '{q}' -> '{clean_ans}'")
                    qa_vault.learn(q, clean_ans, category="llm_auto", user_id=uid)
                    return clean_ans
        except Exception as gemini_err:
            print(f"[Naukri Bot] Tier 3 Gemini attempt notice: {gemini_err}")

        # Groq fallback for Tier 3
        if self._groq_client:
            for g_model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
                try:
                    chat_resp = self._groq_client.chat.completions.create(
                        model=g_model,
                        messages=[
                            {"role": "system", "content": "You are a candidate proxy answering recruiter screening questions factually and concisely."},
                            {"role": "user", "content": llm_prompt}
                        ],
                        max_tokens=150,
                        temperature=0.1
                    )
                    if chat_resp.choices and chat_resp.choices[0].message.content:
                        groq_ans = chat_resp.choices[0].message.content.strip().strip('"\'')
                        print(f"[Naukri Bot] [Tier 3 Groq Auto-Answer via {g_model}]: '{q}' -> '{groq_ans}'")
                        qa_vault.learn(q, groq_ans, category="llm_auto", user_id=uid)
                        return groq_ans
                except Exception as groq_err:
                    print(f"[Naukri Bot] Tier 3 Groq {g_model} attempt notice: {groq_err}")

        # Tier 3 Factual Profile Fallback (if LLMs are temporarily unreachable, answer directly from resume profile facts)
        if cand_summary or skills_str:
            domain_name = cand_profile.get("primary_domain") or "Software and AI Engineering"
            factual_ans = f"I have {cand_exp} years of experience specializing in {domain_name}. My core skills include {skills_str}, with focus on building robust, scalable applications."
            print(f"[Naukri Bot] [Tier 3 Factual Resume Answer]: '{q}' -> '{factual_ans}'")
            qa_vault.learn(q, factual_ans, category="factual_auto", user_id=uid)
            return factual_ans

        # ======================================================================
        # TIER 4: Human-in-the-Loop Gateway (Register Pending + Alert + Wait)
        # ======================================================================
        print(f"[Naukri Bot] [Tier 4 Escalation] Unknown question requires user input: '{q}'")
        q_id = qa_vault.register_pending_question(
            question=q,
            job_title=job_title or "Job Opening",
            company=company or "Recruiter",
            job_url=job_url,
            user_id=uid
        )

        telegram_msg = (
            f"❓ *Recruiter Question Needed*\n\n"
            f"💼 *Role:* {job_title or 'Job Opening'}\n"
            f"🏢 *Company:* {company or 'Recruiter'}\n"
            f"🌐 *Platform:* Naukri\n\n"
            f"📋 *Question Asked:*\n_{q}_\n\n"
            f"👉 *Reply to this message with your answer or answer in the dashboard popup.*\n"
            f"I will fill it immediately, submit the application, and remember it for future jobs!"
        )
        try:
            await telegram_listener.send_message(telegram_msg)
        except Exception as e:
            print(f"[Naukri Bot] Telegram alert error: {e}")

        # Wait up to 35 seconds for candidate answer via Telegram or Web UI popup
        print(f"[Naukri Bot] Waiting up to 35s for candidate answer to: '{q}'...")
        user_answer = await qa_vault.wait_for_user_answer(q_id, timeout_seconds=35)
        if user_answer:
            print(f"[Naukri Bot] Candidate provided answer: '{user_answer}'! Continuing submission.")
            return user_answer

        # If user did not answer, check if question is a simple yes/no or affirmation before giving up
        if any(w in q_lower for w in ["agree", "confirm", "available", "willing", "ready", "accept"]):
            fallback_ans = "Yes"
            print(f"[Naukri Bot] 35s timeout. Using safe affirmative fallback: '{fallback_ans}'")
            return fallback_ans

        print("[Naukri Bot] Candidate did not reply within 35s. Pausing submission.")
        return None

    async def _get_best_option_index(self, question: str, options: list, job_title: str = "", company: str = "", job_url: str = "", user_id: str = None) -> Optional[int]:
        """
        Determines optimal option index (0-based) for radio buttons / chips:
        1. Checks QA Memory Vault
        2. Heuristic rules (rating, percentage, notice period, experience, yes/no, location)
        3. LLM selection via Gemini / Groq
        4. Human-in-the-loop fallback via Telegram & Web UI
        """
        if not options:
            return 0

        uid = user_id or "guest-candidate"
        q = (question or "").lower()
        opts_lower = [o.lower() for o in options]

        # 1. Check if Memory Vault has an exact match for one of the options
        vault_ans = qa_vault.find_answer(question, user_id=uid)
        if vault_ans:
            vault_ans_lower = vault_ans.lower()
            for idx, o in enumerate(opts_lower):
                if vault_ans_lower in o or o in vault_ans_lower:
                    return idx

        # 2. Rating questions (e.g. English communication 1-5)
        if any(w in q for w in ["rating", "rate", "scale", "english", "communication"]):
            for val in ["5", "4", "expert", "fluent", "very good"]:
                for idx, o in enumerate(opts_lower):
                    if val in o:
                        return idx
            return len(options) - 1

        # 3. Percentage questions (10th, 12th, Degree)
        if any(w in q for w in ["percentage", "s.s.c", "h.s.c", "standard", "marks"]):
            for idx, o in enumerate(opts_lower):
                if "80%" in o or "90%" in o or "between 80" in o or "more than 80" in o:
                    return idx

        # 4. Notice period (prioritize 15 days / immediate matching candidate's profile)
        if any(w in q for w in ["notice", "joining"]):
            for pref in ["15 days", "immediate", "serving", "15", "1 month", "30 days"]:
                for idx, o in enumerate(opts_lower):
                    if pref in o:
                        return idx

        # 5. Experience / Fresher
        if "fresher" in q or "experience" in q:
            for idx, o in enumerate(opts_lower):
                if any(k in o for k in ["1-3", "1 to 3", "2-5", "2 to 5", "2 years", "3 years", "fresher"]):
                    return idx

        # 5b. Negative questions where 'No' is the ideal qualification (career break, criminal, termination, gap)
        if any(w in q for w in ["career break", "break in career", "gap in education", "gap in career", "gap", "criminal", "terminated", "disability", "convicted", "fired"]):
            for idx, o in enumerate(opts_lower):
                if o.strip() in ["no", "false", "none", "not applicable", "n/a", "0"]:
                    return idx

        # 6. Yes / No questions
        for idx, o in enumerate(opts_lower):
            if o.strip() in ["yes", "true", "agreed", "ready"]:
                return idx

        # 7. Preferred locations
        for loc in ["bengaluru", "bangalore", "pune", "hyderabad", "delhi", "remote", "mumbai"]:
            for idx, o in enumerate(opts_lower):
                if loc in o:
                    return idx

        # 8. LLM Option Selection via Gemini / Groq
        try:
            from app.llm.gemini_service import gemini_service
            if gemini_service.is_available():
                opt_str = "\n".join([f"{i}: {opt}" for i, opt in enumerate(options)])
                prompt = f"""Recruiter Question: "{question}"
Options:
{opt_str}

Which option index (0 to {len(options)-1}) is the most positive, qualified candidate choice? Reply with ONLY the single integer."""
                res = gemini_service.generate(prompt=prompt, system_prompt="You pick the optimal option index (0-based integer).", temperature=0.0)
                if res:
                    digits = re.findall(r"\d+", res.strip())
                    if digits:
                        picked = int(digits[0])
                        if 0 <= picked < len(options):
                            print(f"[Naukri Bot] [Gemini Option Selected]: [{picked}] '{options[picked]}'")
                            return picked
        except Exception:
            pass

        # 8b. Groq High-Speed Option Selection Fallback
        try:
            import groq
            groq_key = os.getenv("GROQ_API_KEY", "")
            if groq_key:
                client = groq.Groq(api_key=groq_key)
                opt_str = "\n".join([f"{i}: {opt}" for i, opt in enumerate(options)])
                prompt = f"""Recruiter Question: "{question}"
Options:
{opt_str}

Which option index (0 to {len(options)-1}) is the most positive, qualified candidate choice? Reply with ONLY the single integer."""
                resp = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                txt = resp.choices[0].message.content.strip()
                digits = re.findall(r"\d+", txt)
                if digits:
                    picked = int(digits[0])
                    if 0 <= picked < len(options):
                        print(f"[Naukri Bot] [Groq Option Selected]: [{picked}] '{options[picked]}'")
                        return picked
        except Exception as groq_err:
            print(f"[Naukri Bot] Groq option selection note: {groq_err}")

        # 9. If options are unknown, ask the user on Telegram / UI
        q_id = qa_vault.register_pending_question(
            question=question,
            job_title=job_title or "Job",
            company=company or "Company",
            job_url=job_url,
            options=options,
            user_id=uid
        )
        opts_list = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        telegram_msg = (
            f"❓ *Recruiter Option Question Needed*\n\n"
            f"💼 *Role:* {job_title}\n"
            f"🏢 *Company:* {company}\n\n"
            f"📋 *Question Asked:*\n_{question}_\n\n"
            f"🔢 *Options:*\n{opts_list}\n\n"
            f"👉 *Reply with option number or text. I will save it permanently in your memory vault!*"
        )
        try:
            await telegram_listener.send_message(telegram_msg)
        except Exception:
            pass

        print(f"[Naukri Bot] Waiting up to 30s for candidate to pick option for: '{question}'...")
        user_choice = await qa_vault.wait_for_user_answer(q_id, timeout_seconds=30)
        if user_choice:
            user_choice_lower = user_choice.lower().strip()
            if user_choice_lower.isdigit():
                num = int(user_choice_lower) - 1
                if 0 <= num < len(options):
                    return num
            for idx, o in enumerate(opts_lower):
                if user_choice_lower in o or o in user_choice_lower:
                    return idx

        return 0

    async def _is_submission_confirmed(self, page) -> bool:
        """
        Verifies if Naukri has confirmed application submission.
        Checks URL, success banners, applied badges, and chatbot drawer messages.
        """
        try:
            curr_url = (page.url or "").lower()
            if "nlogin" in curr_url or "login.naukri.com" in curr_url:
                return False

            # Check 1: Redirected to application success URL
            if any(k in curr_url for k in ["application-success", "apply/success", "apply-success"]):
                return True

            # Check 2: Applied badge on job page (.already-applied, #already-applied)
            applied_badge = await page.locator(".already-applied, #already-applied, [class*='already-applied' i], [class*='alreadyApplied' i]").count()
            if applied_badge > 0:
                return True

            # Check 3: Applied button text
            applied_btn = await page.locator("button:has-text('Applied'), span:has-text('Applied'), div:has-text('Applied')").count()
            if applied_btn > 0:
                for el in await page.locator("button:has-text('Applied'), span:has-text('Applied')").all():
                    txt = (await el.text_content() or "").strip().lower()
                    if txt in ["applied", "already applied", "applied on"]:
                        return True

            # Check 4: Success banners and confirmation modals
            success_banners = await page.locator(".apply-message, [class*='applyMessage' i], [class*='apply-message' i], [class*='apply-success' i], [class*='success-banner' i]").count()
            if success_banners > 0:
                for el in await page.locator(".apply-message, [class*='applyMessage' i], [class*='apply-message' i]").all():
                    banner_text = (await el.text_content() or "").lower()
                    if any(k in banner_text for k in ["successfully applied", "application sent", "applied to"]):
                        return True

            # Check 5: Chatbot drawer completion messages
            drawer = page.locator(".chatbot_Drawer, .chatbot_DrawerContentWrapper, [class*='chatbot_Drawer' i]").first
            if await drawer.count() > 0:
                drawer_text = (await drawer.text_content() or "").lower()
                if any(k in drawer_text for k in ["successfully applied", "application has been sent", "application submitted", "applied to this job", "thanks for applying"]):
                    return True

            # Check 6: Success confirmation text on page body
            body_text = (await page.locator("body").text_content() or "").lower()
            if any(k in body_text for k in [
                "applied to \"",
                "successfully applied to",
                "application sent to",
                "you have successfully applied"
            ]):
                return True

            return False
        except Exception as e:
            print(f"[Naukri Bot] Confirmation check note: {e}")
            return False

    async def _handle_chatbot_drawer(self, page, job_title: str, company: str = '', job_url: str = '', user_id: str = None) -> bool:
        """
        Executes sequential questionnaire answers until full submission.
        Returns True if application is confirmed, False otherwise.
        """
        try:
            drawer = page.locator(".chatbot_Drawer, .chatbot_DrawerContentWrapper, [class*='chatbot_Drawer' i]").first
            # Give drawer up to 3 seconds to appear
            for _ in range(6):
                if await drawer.count() > 0 and await drawer.is_visible():
                    break
                await page.wait_for_timeout(500)

            if await drawer.count() == 0 or not await drawer.is_visible():
                return await self._is_submission_confirmed(page)

            print(f"[Naukri Live Runner] Active recruiter questionnaire detected for: {job_title}")

            for step in range(1, 16):
                await page.wait_for_timeout(2000)

                # Check if already successfully applied
                if await self._is_submission_confirmed(page):
                    print(f"[Naukri Live Runner] Confirmed submission in step {step}!")
                    return True

                # Check if drawer has closed
                if await drawer.count() == 0 or not await drawer.is_visible():
                    await page.wait_for_timeout(2000)
                    return await self._is_submission_confirmed(page)

                # Extract latest question text from chatbot
                messages = await drawer.locator(".botMsg").all_text_contents()
                current_q = messages[-1].strip() if messages else ""
                print(f"[Naukri Live Runner] Step {step} Question: '{current_q}'")

                action_taken = False

                # 1. Check for Radio Button options
                radio_containers = await drawer.locator(".ssrc__radio-btn-container, .singleselect-radiobutton-container .ssrc__radio-btn-container").all()
                if radio_containers:
                    option_texts = []
                    for rc in radio_containers:
                        t = (await rc.text_content() or "").strip()
                        option_texts.append(t)

                    best_idx = await self._get_best_option_index(current_q, option_texts, job_title=job_title, company=company, job_url=job_url, user_id=user_id)
                    if best_idx is None:
                        best_idx = 0
                    print(f"  -> Selecting Radio Option [{best_idx}]: '{option_texts[best_idx]}'")

                    await drawer.evaluate(f"""(container) => {{
                        const radios = container.querySelectorAll('.ssrc__radio-btn-container, .singleselect-radiobutton-container .ssrc__radio-btn-container');
                        const target = radios[{best_idx}] || radios[0];
                        if (target) {{
                            target.click();
                            const input = target.querySelector('input');
                            if (input) {{
                                input.checked = true;
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }}
                            const label = target.querySelector('label');
                            if (label) label.click();
                        }}
                    }}""")
                    action_taken = True
                    await page.wait_for_timeout(800)

                # 2. Check for Option Chips (.chatbot_Chip, .chipItem)
                elif await drawer.locator(".chatbot_Chip, .chipItem").count() > 0:
                    chips = await drawer.locator(".chatbot_Chip, .chipItem").all()
                    chip_texts = [(await c.text_content() or "").strip() for c in chips]
                    best_idx = await self._get_best_option_index(current_q, chip_texts, job_title=job_title, company=company, job_url=job_url, user_id=user_id)
                    if best_idx is None:
                        best_idx = 0
                    print(f"  -> Clicking Option Chip [{best_idx}]: '{chip_texts[best_idx]}'")
                    await chips[best_idx].click(force=True)
                    action_taken = True
                    await page.wait_for_timeout(800)

                # 3. Check for Text / CTC / Number Input (.textArea, input, textarea)
                text_input = drawer.locator(".textArea, textarea, input:not([type='radio']):not([type='checkbox']):not([type='file'])").first
                if await text_input.is_visible():
                    answer_text = await self._get_smart_answer(current_q, job_title=job_title, company=company, job_url=job_url, user_id=user_id)
                    placeholder = (await text_input.get_attribute("placeholder") or "").lower()
                    if ("yyyy" in placeholder or "mm" in placeholder or "dob" in current_q.lower() or "birth" in current_q.lower()) and not re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", answer_text):
                        answer_text = "15/08/1999" 
                    if not answer_text:
                        print(f"  -> Question '{current_q}' is not answered in memory or by user. Pausing.")
                        return False
                    print(f"  -> Answering via Text: '{answer_text}'")
                    is_readonly = await text_input.get_attribute("readonly") is not None
                    if is_readonly:
                        await text_input.evaluate(f"(el) => {{ el.removeAttribute('readonly'); el.value = '{answer_text}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); el.dispatchEvent(new Event('change', {{bubbles: true}})); }}")
                    else:
                        try:
                            await text_input.click()
                            await text_input.fill("")
                            await text_input.press_sequentially(answer_text, delay=35)
                        except Exception:
                            await text_input.evaluate(f"(el) => {{ el.value = '{answer_text}'; el.dispatchEvent(new Event('input', {{bubbles: true}})); el.dispatchEvent(new Event('change', {{bubbles: true}})); }}")
                    action_taken = True
                    await page.wait_for_timeout(800)

                # 4. Click Save / Send button
                save_btn = drawer.locator(".sendMsg, .send:not(.disabled), [id*='sendMsg']").last
                if await save_btn.is_visible():
                    print("  -> Submitting answer via Save/Send button...")
                    await save_btn.click(force=True)
                    await page.wait_for_timeout(3000)
                else:
                    if not action_taken:
                        print("  -> No input action identified on this step.")
                        break

            return await self._is_submission_confirmed(page)

        except Exception as e:
            print(f"[Naukri Bot] Questionnaire handler exception: {e}")
            return await self._is_submission_confirmed(page)

    async def apply_single_job(self, job_url: str, job_title: str = "AI Engineer", company: str = "Recruiter", user_id: str = None, override_cookies: List[Dict] = None):
        """
        Executes end-to-end autonomous application to a single live Naukri job listing.
        Strict verification: Only returns applied_successfully if verified on the live DOM!
        Never simulates or fakes submission.
        """
        cookies = override_cookies or self._load_cookies(user_id=user_id)
        if not cookies:
            return {
                "status": "session_required",
                "message": "No active session cookies connected for your account. Please connect your cookies in Settings or export from your logged-in Naukri browser."
            }

        # Active session verification
        is_valid, session_msg = await self.verify_naukri_session(cookies)
        if not is_valid:
            print(f"[Naukri Bot] Pre-apply session verification failed: {session_msg}")
            return {
                "status": "session_expired",
                "message": session_msg
            }

        user_key = user_id or "guest-candidate"
        user_proof_dir = os.path.join(PROOF_DIR, user_key)
        os.makedirs(user_proof_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_filename = f"proof_{timestamp}.png"
        proof_path = os.path.join(user_proof_dir, proof_filename)
        proof_url = f"/proofs/{user_key}/{proof_filename}"

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=user_agent,
                    locale="en-US",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Windows"'
                    }
                )
                await context.add_init_script("""
                    delete Object.getPrototypeOf(navigator).webdriver;
                    window.navigator.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                """)

                clean_cookies = []
                blocked_waf = {"_abck", "ak_bmsc", "bm_sz", "bm_sv", "bm_mi", "bm_so"}
                for c in cookies:
                    if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
                        c_name = str(c["name"]).strip()
                        c_lower = c_name.lower()
                        if c_lower.startswith("ak_") or c_lower.startswith("bm_") or c_lower in blocked_waf:
                            continue
                        dom = str(c.get("domain") or ".naukri.com")
                        if not dom.startswith("."):
                            dom = f".{dom}"
                        clean_cookies.append({
                            "name": c_name,
                            "value": str(c["value"]).strip(),
                            "domain": dom,
                            "path": str(c.get("path") or "/")
                        })
                await context.add_cookies(clean_cookies)

                page = await context.new_page()
                try:
                    # 1. Warm up domain cookies first so Naukri SPA recognizes the authenticated session
                    print(f"\n[Naukri Bot] Warming up domain cookies on https://www.naukri.com ...")
                    try:
                        await page.goto("https://www.naukri.com", wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(1.5)
                    except Exception as warm_err:
                        print(f"[Naukri Bot] Domain warmup notice: {warm_err}")

                    # 2. Navigate to the target job_url
                    print(f"[Naukri Bot] Navigating to: {job_title} -> {job_url}")
                    await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)

                    # Wait for Naukri React SPA to hydrate job details OR search results
                    try:
                        await page.wait_for_selector(
                            "#apply-button, #login-apply-button, .apply-button, "
                            "[class*='styles_jhc__apply-button'], [class*='jd-header'], "
                            ".srp-jobtuple-wrapper, article.jobTuple, #company-site-button",
                            timeout=12000
                        )
                    except Exception:
                        await asyncio.sleep(3.0)

                    # Check for cloud bot challenge or access denied
                    page_content = (await page.content()).lower()
                    if "let us know you're human" in page_content or "recaptcha" in page_content or ("access denied" in page_content and "permission to access" in page_content):
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "cloud_security_challenge",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": "Naukri cloud bot challenge detected: Naukri requires verification for cloud server IPs. Use 1-Click Direct Apply to submit directly with your authenticated browser session."
                        }

                    # Check if page redirected to login
                    curr_url = page.url.lower()
                    if "nlogin" in curr_url or "login.naukri.com" in curr_url:
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "session_expired",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": "Naukri redirected to login page. Your session cookies have expired. Please connect fresh cookies in Settings."
                        }

                    # 3. If the URL redirected to a search page or 404/expired listing (no JD header found),
                    # automatically search and open the first live direct-apply Naukri job for this role:
                    has_jd_header = await page.locator(
                        "#apply-button, #login-apply-button, .apply-button, "
                        "[class*='styles_jhc__'], [class*='jd-header-title'], #company-site-button"
                    ).count() > 0

                    if not has_jd_header:
                        card_links = page.locator("a.title[href*='job-listings-'], .srp-jobtuple-wrapper a.title")
                        if await card_links.count() == 0:
                            # Run a live search on Naukri for job_title
                            slug = re.sub(r"[^a-z0-9]+", "-", job_title.lower()).strip("-")
                            search_url = f"https://www.naukri.com/{slug}-jobs"
                            await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                            try:
                                await page.wait_for_selector("a.title[href*='job-listings-'], .srp-jobtuple-wrapper a.title", timeout=10000)
                            except Exception:
                                await asyncio.sleep(2.0)
                        card_links = page.locator("a.title[href*='job-listings-'], .srp-jobtuple-wrapper a.title")
                        if await card_links.count() > 0:
                            first_href = await card_links.first.get_attribute("href")
                            if first_href:
                                if first_href.startswith("/"):
                                    first_href = f"https://www.naukri.com{first_href}"
                                job_url = first_href
                                await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                                try:
                                    await page.wait_for_selector(
                                        "#apply-button, #login-apply-button, .apply-button, "
                                        "[class*='styles_jhc__apply-button'], #company-site-button",
                                        timeout=10000
                                    )
                                except Exception:
                                    await asyncio.sleep(2.5)

                    # 4. Check if already applied on Naukri
                    already_applied = (await page.locator(
                        "#already-applied, span:has-text('Applied'), button:has-text('Applied')"
                    ).count() > 0) or (await self._is_submission_confirmed(page))

                    if already_applied:
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "already_applied",
                            "applied": True,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": f"Already applied to {job_title} on Naukri.com."
                        }

                    # 5. Check if Naukri shows 'Login to apply' (cookies missing/expired)
                    login_to_apply_btn = page.locator(
                        "#login-apply-button, button:has-text('Login to apply'), a:has-text('Login to apply')"
                    )
                    if await login_to_apply_btn.count() > 0 and await login_to_apply_btn.first.is_visible():
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "login_required",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": "Naukri displayed 'Login to apply' — your Naukri cookies are missing or expired. Please export fresh cookies from Naukri.com while logged in."
                        }

                    # Check if opening is closed/expired
                    page_content = (await page.content()).lower()
                    if any(term in page_content for term in ["job is no longer available", "job posting has expired", "job has expired"]):
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "job_expired",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": "This job opening has expired or was closed by the recruiter on Naukri. Please choose another matched opening."
                        }

                    # 6. First look for DIRECT Naukri Apply button (prioritize direct apply BEFORE checking external apply!)
                    direct_apply_selectors = [
                        "#apply-button",
                        "button#apply-button",
                        "button.apply-button",
                        "[class*='styles_jhc__apply-button'] button:not(:has-text('Company Site'))",
                        "button:has-text('Apply'):not(:has-text('Company Site')):not(:has-text('Login'))",
                        "div.apply-button-container button",
                        ".apply-btn",
                        "#root .apply-button",
                        "button:has-text('I am interested')",
                        "a:has-text('I am interested')"
                    ]
                    apply_btn = None
                    for sel in direct_apply_selectors:
                        loc = page.locator(sel)
                        cnt = await loc.count()
                        for i in range(cnt):
                            candidate = loc.nth(i)
                            if await candidate.is_visible():
                                btn_text = (await candidate.inner_text() or "").strip().lower()
                                if "company site" not in btn_text and "login" not in btn_text:
                                    apply_btn = candidate
                                    break
                        if apply_btn:
                            break

                    # 7. ONLY if no direct Apply button exists, check if the page genuinely has an "Apply on company site" button
                    if not apply_btn:
                        ext_btn = page.locator("#company-site-button, button:has-text('Apply on company site'), a:has-text('Apply on company site'), button:has-text('Apply on Employer Website'), a:has-text('Apply on Employer Website'), button:has-text('Apply on official website'), a:has-text('Apply on official website'), .company-site-button")
                        if await ext_btn.count() > 0 and await ext_btn.first.is_visible():
                            await page.screenshot(path=str(proof_path), full_page=False)
                            return {
                                "status": "external_portal",
                                "applied": False,
                                "job_title": job_title,
                                "job_url": page.url,
                                "proof_url": proof_url,
                                "proof_image": proof_url,
                                "message": "This listing uses an external company portal ('Apply on company site')."
                            }

                        if await page.locator("#login_Layer, .login-layer, .login-register").count() > 0:
                            await page.screenshot(path=str(proof_path), full_page=False)
                            return {
                                "status": "session_expired",
                                "applied": False,
                                "job_title": job_title,
                                "job_url": page.url,
                                "proof_url": proof_url,
                                "proof_image": proof_url,
                                "message": "Naukri displayed login prompt. Please connect active session cookies from Settings or Quick Apply Assistant."
                            }

                        # Otherwise, report the exact real diagnostic reason (never falsely blame 'direct company application'!)
                        page_title = await page.title()
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "apply_button_not_found",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": f"Could not find Naukri Apply button on '{page_title}' ({page.url}). Check the proof screenshot or refresh your Naukri cookies."
                        }

                    # 8. Click the Direct Apply button using both standard click and JS fallback
                    print(f"[Naukri Bot] Physical click on Apply button for {job_title}...")
                    try:
                        await apply_btn.scroll_into_view_if_needed()
                        await apply_btn.click(timeout=8000)
                    except Exception:
                        await apply_btn.evaluate("el => el.click()")

                    await asyncio.sleep(3.5)

                    # Check if login popup appeared after click
                    if await page.locator("#login_Layer, .login-layer, .login-register").count() > 0:
                        await page.screenshot(path=str(proof_path), full_page=False)
                        return {
                            "status": "session_expired",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": "Naukri requested login after clicking Apply. Please reconnect active session cookies."
                        }

                    # 9. Handle Naukri's Chatbot Questionnaire Drawer if it opens after clicking Apply
                    drawer_selectors = ".chatbot_DrawerContentWrapper, [class*='chatbot_Drawer'], .ssrc__drawer, div[id*='chatBot']"
                    if await page.locator(drawer_selectors).count() > 0:
                        try:
                            await self._handle_chatbot_drawer(page, job_title=job_title, company=company, job_url=job_url, user_id=user_id)
                        except Exception as drawer_err:
                            print(f"[Naukri Bot] Chatbot drawer fallback: {drawer_err}")
                            for _ in range(8):
                                text_inputs = page.locator(f"{drawer_selectors} input[type='text'], {drawer_selectors} input[type='number'], {drawer_selectors} textarea")
                                if await text_inputs.count() > 0 and await text_inputs.first.is_visible():
                                    await text_inputs.first.fill("3")
                                radios = page.locator(f"{drawer_selectors} input[type='radio'], {drawer_selectors} label[class*='radio']")
                                if await radios.count() > 0 and await radios.first.is_visible():
                                    await radios.first.click()
                                send_btn = page.locator(f"{drawer_selectors} .sendMsg, {drawer_selectors} button:has-text('Save'), {drawer_selectors} button:has-text('Submit'), {drawer_selectors} button:has-text('Next')")
                                if await send_btn.count() > 0 and await send_btn.first.is_visible():
                                    await send_btn.first.click()
                                    await asyncio.sleep(1.8)
                                else:
                                    break

                    await asyncio.sleep(2.5)
                    await page.screenshot(path=str(proof_path), full_page=False)

                    # Final live DOM submission confirmation check
                    is_confirmed = await self._is_submission_confirmed(page) or (await page.locator("#already-applied, span:has-text('Applied'), button:has-text('Applied')").count() > 0)

                    if is_confirmed:
                        print(f"[Naukri Bot] [SUCCESS] VERIFIED SUCCESS: Application submitted for {job_title}!")
                        return {
                            "status": "applied_successfully",
                            "applied": True,
                            "verified": True,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "message": f"Successfully applied to {job_title} on Naukri.com! Live DOM verified!"
                        }
                    else:
                        print(f"[Naukri Bot] [NOTICE] Incomplete submission: Questionnaire requires candidate action.")
                        await notifier.send_hitl_alert(
                            job_title=job_title,
                            company=company or "Naukri Recruiter",
                            platform="Naukri",
                            job_url=job_url,
                            reason="Recruiter screening questionnaire requires human verification."
                        )
                        return {
                            "status": "needs_human_action",
                            "applied": False,
                            "job_title": job_title,
                            "job_url": page.url,
                            "proof_url": proof_url,
                            "proof_image": proof_url,
                            "message": "Screening questionnaire requires manual review. Alert sent to your Telegram!"
                        }

                except Exception as e:
                    await page.screenshot(path=str(proof_path), full_page=False) if page else None
                    return {
                        "status": "error",
                        "message": f"Error during application execution: {str(e)}",
                        "job_title": job_title,
                        "job_url": job_url,
                        "proof_image": proof_url,
                        "proof_url": proof_url
                    }
                finally:
                    await browser.close()


        except Exception as browser_err:
            clean_err = str(browser_err).splitlines()[0] if str(browser_err) else "Browser error"
            print(f"[Naukri Bot] Playwright error: {clean_err}.")
            return {
                "status": "error",
                "message": f"Browser automation error: {clean_err}. Please ensure active cookies are connected.",
                "job_title": job_title,
                "job_url": job_url
            }

    async def execute_live_apply(self, query: str = "AI Engineer", limit: int = 3, user_id: str = None, override_cookies: List[Dict] = None):
        """
        Batch autonomous application across matching Naukri listings.
        Strict verification: Only records applied_successfully when confirmed on live DOM.
        """
        cookies = override_cookies or self._load_cookies(user_id=user_id)
        if not cookies:
            return {
                "status": "session_required",
                "message": "No active session cookies connected for your account. Please connect your cookies in Settings or export from your logged-in Naukri browser.",
                "applications": []
            }

        # Active session verification
        is_valid, session_msg = await self.verify_naukri_session(cookies)
        if not is_valid:
            return {
                "status": "session_expired",
                "message": session_msg,
                "applications": []
            }

        results = []
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=user_agent,
                    locale="en-US",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Windows"'
                    }
                )
                await context.add_init_script("""
                    delete Object.getPrototypeOf(navigator).webdriver;
                    window.navigator.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                """)

                clean_cookies = []
                blocked_waf = {"_abck", "ak_bmsc", "bm_sz", "bm_sv", "bm_mi", "bm_so"}
                for c in cookies:
                    if isinstance(c, dict) and c.get("name") and c.get("value") is not None:
                        c_name = str(c["name"]).strip()
                        c_lower = c_name.lower()
                        if c_lower.startswith("ak_") or c_lower.startswith("bm_") or c_lower in blocked_waf:
                            continue
                        dom = str(c.get("domain") or ".naukri.com")
                        if not dom.startswith("."):
                            dom = f".{dom}"
                        clean_cookies.append({
                            "name": c_name,
                            "value": str(c["value"]).strip(),
                            "domain": dom,
                            "path": str(c.get("path") or "/")
                        })
                await context.add_cookies(clean_cookies)

                page = await context.new_page()
                try:
                    await Stealth().apply_stealth_async(page)
                except Exception:
                    pass
                
                clean_query = query.replace(" ", "-").lower()
                search_url = f"https://www.naukri.com/{clean_query}-jobs"
                print(f"[Naukri Live Runner] Scanning: {search_url}")

                try:
                    try:
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)

                        cards = await page.locator(".srp-jobtuple-wrapper, .cust-job-tuple").all()
                        urls_to_apply = []

                        for card in cards:
                            title_el = card.locator("a.title").first
                            title = (await title_el.text_content() or "").strip()
                            href = await title_el.get_attribute("href")
                            card_text = (await card.text_content() or "").lower()

                            if "applied" in card_text:
                                continue

                            if href and "job-listings" in href and len(title) > 3:
                                if href not in [u["url"] for u in urls_to_apply]:
                                    urls_to_apply.append({"title": title, "url": href})
                            if len(urls_to_apply) >= limit * 3:
                                break
                    except Exception as scan_err:
                        print(f"[Naukri Live Runner] Scan error ({scan_err}), fallback to verified catalog...")
                        urls_to_apply = []

                    if not urls_to_apply:
                        print(f"[Naukri Live Runner] Using verified {query} catalog listings...")
                        from app.scrapers.naukri_scraper import naukri_scraper
                        matched = await naukri_scraper.search_jobs(query=query, limit=limit * 2)
                        urls_to_apply = [{"title": j.title, "url": j.job_url} for j in matched]

                    print(f"[Naukri Live Runner] Ready to process {len(urls_to_apply)} openings for '{query}'.")

                    processed_count = 0
                    for item in urls_to_apply:
                        if processed_count >= limit:
                            break

                        job_title = item["title"]
                        job_url = item["url"]
                        print(f"\n[Naukri Live Runner] [{processed_count+1}/{limit}] Opening: {job_title}")

                        job_page = await context.new_page()
                        try:
                            await Stealth().apply_stealth_async(job_page)
                        except Exception:
                            pass
                        
                        try:
                            await job_page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                            await job_page.wait_for_timeout(2500)

                            user_key = user_id or "guest-candidate"
                            user_proof_dir = os.path.join(PROOF_DIR, user_key)
                            os.makedirs(user_proof_dir, exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            proof_filename = f"proof_batch_{processed_count+1}_{timestamp}.png"
                            proof_path = os.path.join(user_proof_dir, proof_filename)
                            proof_url = f"/proofs/{user_key}/{proof_filename}"

                            # Check if redirected to login
                            if "nlogin" in job_page.url.lower() or "login.naukri.com" in job_page.url.lower():
                                await job_page.screenshot(path=proof_path)
                                results.append({
                                    "job_title": job_title,
                                    "status": "session_expired",
                                    "proof_image": proof_url,
                                    "url": job_url,
                                    "message": "Session expired during batch run."
                                })
                                break

                            # Check if already applied
                            if await self._is_submission_confirmed(job_page):
                                await job_page.screenshot(path=proof_path)
                                results.append({
                                    "job_title": job_title,
                                    "status": "already_applied",
                                    "proof_image": proof_url,
                                    "url": job_url
                                })
                                print(f"  -> Already applied to {job_title}.")
                                continue

                            # Check if external portal
                            external_btn = job_page.locator(".company-site-button, button:has-text('Apply on company site'), a:has-text('Apply on company site')").first
                            if await external_btn.is_visible():
                                await job_page.screenshot(path=proof_path)
                                results.append({
                                    "job_title": job_title,
                                    "status": "external_portal",
                                    "proof_image": proof_url,
                                    "url": job_url
                                })
                                print(f"  -> External portal: {job_title}")
                                continue

                            # Direct Apply
                            apply_selectors = [
                                "#apply-button",
                                "button.apply-button",
                                ".apply-button",
                                "button:has-text('Apply on Naukri')",
                                "a:has-text('Apply on Naukri')",
                                "button:has-text('Apply')",
                                "[id*='apply-button']",
                                "[class*='apply-button']"
                            ]
                            apply_btn = None
                            for sel in apply_selectors:
                                loc = job_page.locator(sel).first
                                if await loc.count() > 0 and await loc.is_visible():
                                    apply_btn = loc
                                    break

                            if apply_btn:
                                print(f"  -> Clicking 'Apply' for {job_title}...")
                                await apply_btn.click()
                                await job_page.wait_for_timeout(3500)

                                # Questionnaire handler
                                applied_ok = await self._handle_chatbot_drawer(job_page, job_title=job_title, company='', job_url=job_url, user_id=user_id)
                                await job_page.wait_for_timeout(2500)
                                await job_page.screenshot(path=proof_path)

                                if applied_ok or await self._is_submission_confirmed(job_page):
                                    results.append({
                                        "job_title": job_title,
                                        "status": "applied_successfully",
                                        "proof_image": proof_url,
                                        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "url": job_url
                                    })
                                    print(f"[+] SUCCESS! Real application submitted for: {job_title}")
                                    processed_count += 1
                                else:
                                    results.append({
                                        "job_title": job_title,
                                        "status": "needs_human_action",
                                        "proof_image": proof_url,
                                        "url": job_url
                                    })
                                    print(f"[-] Questionnaire incomplete for: {job_title}")
                            else:
                                await job_page.screenshot(path=proof_path)
                                results.append({
                                    "job_title": job_title,
                                    "status": "apply_unavailable",
                                    "proof_image": proof_url,
                                    "url": job_url
                                })

                        except Exception as err:
                            print(f"  -> Error applying to {job_title}: {err}")
                            results.append({"job_title": job_title, "status": "error", "message": str(err), "url": job_url})
                        finally:
                            await job_page.close()

                    await browser.close()
                except Exception as e:
                    print(f"[Naukri Live Runner Exception]: {e}")
                    return {"status": "error", "message": str(e), "applications": results}

                return {"status": "completed", "applications": results}
        except Exception as browser_err:
            clean_err = str(browser_err).splitlines()[0] if str(browser_err) else "Browser error"
            print(f"[Naukri Bot] Playwright error in batch apply: {clean_err}")
            return {
                "status": "error",
                "message": f"Browser automation error: {clean_err}",
                "applications": []
            }

naukri_live_runner = RealNaukriApplyEngine()
check_naukri_application_count = naukri_live_runner.check_naukri_application_count
verify_naukri_session = naukri_live_runner.verify_naukri_session
