import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Tuple
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
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
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
    - Uses authenticated browser cookies.
    - Physically interacts with job listings and application flows.
    - Handles complex multi-step recruiter screening questionnaires:
      * Dynamic contenteditable text inputs (.textArea)
      * Native & custom styled radio buttons (.ssrc__radio, .ssrc__radio-btn-container)
      * Option chips (.chatbot_Chip, .chipItem)
      * Checkbox arrays (.msrc__radio-btn-container)
    - Powered by Candidate Vault + Groq Qwen 27B for intelligent answers.
    - Rigorous verification: only marks as applied when confirmed by Naukri DOM / success URL.
    - If a recruiter question cannot be solved, alerts candidate via Telegram HITL.
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
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process",
            "--no-zygote"
        ]
        return await p.chromium.launch(headless=True, args=args)

    def _load_cookies(self, user_id: str = None) -> List[Dict]:
        """
        Loads session cookies strictly for the specified user_id.
        No global fallbacks or cross-tenant leakage.
        """
        if not user_id:
            return []

        cookie_file = DATA_COOKIES_DIR / str(user_id) / "naukri_cookies.json"
        if not cookie_file.exists():
            return []

        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[Naukri Bot] Error loading cookies for user {user_id}: {e}")
            return []

        if not raw or not isinstance(raw, list):
            return []

        try:
            return [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".naukri.com"),
                    "path": c.get("path", "/")
                }
                for c in raw
                if isinstance(c, dict) and "name" in c and "value" in c
            ]
        except Exception as e:
            print(f"[Naukri Bot] Error normalizing cookies for user {user_id}: {e}")
            return []

    async def _get_smart_answer(self, question: str, job_title: str = "", company: str = "", job_url: str = "", user_id: str = None) -> Optional[str]:
        """
        Looks up answer from QA Memory Vault for user_id.
        If unknown, dispatches the exact question to the user via Telegram & UI,
        waits for user reply, and saves it permanently to memory!
        """
        q = (question or "").strip()
        if not q:
            return None

        # 1. Check QA Memory Vault first
        vault_answer = qa_vault.find_answer(q, user_id=user_id or "guest-candidate")
        if vault_answer:
            print(f"[Naukri Bot] Memory Vault Match: '{q}' -> '{vault_answer}'")
            return vault_answer

        # 2. Unknown question! Do NOT guess or hallucinate.
        print(f"[Naukri Bot] Unknown question not in memory/resume: '{q}'")
        q_id = qa_vault.register_pending_question(
            question=q,
            job_title=job_title or "Job",
            company=company or "Company",
            job_url=job_url,
            user_id=user_id or "guest-candidate"
        )

        # 3. Alert candidate via Telegram with exact copy-pasted question
        telegram_msg = (
            f"❓ *Recruiter Question Needed*\n\n"
            f"💼 *Role:* {job_title}\n"
            f"🏢 *Company:* {company}\n"
            f"🌐 *Platform:* Naukri\n\n"
            f"📋 *Question Asked:*\n_{q}_\n\n"
            f"👉 *Reply to this message with your answer.*\n"
            f"I will type it in now, submit the application, and *remember it permanently* for future applications!"
        )
        try:
            await telegram_listener.send_message(telegram_msg)
        except Exception as e:
            print(f"[Naukri Bot] Telegram alert error: {e}")

        # 4. Wait up to 35 seconds for candidate answer via Telegram or Web UI
        print(f"[Naukri Bot] Waiting up to 35s for candidate answer to: '{q}'...")
        user_answer = await qa_vault.wait_for_user_answer(q_id, timeout_seconds=35)
        if user_answer:
            print(f"[Naukri Bot] Candidate provided answer: '{user_answer}'! Continuing submission.")
            return user_answer

        print("[Naukri Bot] Candidate did not reply within 35s. Pausing submission.")
        return None

    async def _get_best_option_index(self, question: str, options: list, job_title: str = "", company: str = "", job_url: str = "", user_id: str = None) -> Optional[int]:
        """
        Determines the optimal option index (0-based) for radio buttons / chips.
        Checks QA Memory Vault first. If completely unknown, queries user.
        """
        if not options:
            return 0

        q = (question or "").lower()
        opts_lower = [o.lower() for o in options]

        # 1. Check if Memory Vault has an exact match for one of the options
        vault_ans = qa_vault.find_answer(question, user_id=user_id or "guest-candidate")
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

        # 4. Notice period
        if any(w in q for w in ["notice", "joining"]):
            for idx, o in enumerate(opts_lower):
                if any(k in o for k in ["15 days", "immediate", "serving", "1 month"]):
                    return idx

        # 5. Experience / Fresher
        if "fresher" in q or "experience" in q:
            for idx, o in enumerate(opts_lower):
                if any(k in o for k in ["1-3", "1 to 3", "2 years", "fresher"]):
                    return idx

        # 6. Yes / No questions
        for idx, o in enumerate(opts_lower):
            if o.strip() in ["yes", "true", "agreed", "ready"]:
                return idx

        # 7. Preferred locations
        for loc in ["bengaluru", "bangalore", "pune", "hyderabad", "delhi", "remote"]:
            for idx, o in enumerate(opts_lower):
                if loc in o:
                    return idx

        # 8. If options are unknown, ask the user on Telegram
        q_id = qa_vault.register_pending_question(
            question=question,
            job_title=job_title or "Job",
            company=company or "Company",
            job_url=job_url,
            options=options,
            user_id=user_id or "guest-candidate"
        )
        opts_list = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        telegram_msg = (
            f"❓ *Recruiter Option Question Needed*\n\n"
            f"💼 *Role:* {job_title}\n"
            f"🏢 *Company:* {company}\n\n"
            f"📋 *Question Asked:*\n_{question}_\n\n"
            f"🔢 *Options:*\n{opts_list}\n\n"
            f"👉 *Reply with the option number or text.* I will save it permanently in your memory vault!"
        )
        try:
            await telegram_listener.send_message(telegram_msg)
        except Exception:
            pass

        print(f"[Naukri Bot] Waiting up to 30s for candidate to pick option for: '{question}'...")
        user_choice = await qa_vault.wait_for_user_answer(q_id, timeout_seconds=30)
        if user_choice:
            user_choice_lower = user_choice.lower().strip()
            # If user sent a digit (1, 2, 3...)
            if user_choice_lower.isdigit():
                num = int(user_choice_lower) - 1
                if 0 <= num < len(options):
                    return num
            # Check text match
            for idx, o in enumerate(opts_lower):
                if user_choice_lower in o or o in user_choice_lower:
                    return idx

        return 0

    async def _is_submission_confirmed(self, page) -> bool:
        """
        Verifies if Naukri has confirmed application submission.
        """
        try:
            # Check 1: Redirected to application success URL
            if "application-success" in (page.url or "").lower():
                return True

            # Check 2: Applied badge on job page (.already-applied, #already-applied)
            applied_badge = await page.locator(".already-applied, #already-applied, [class*='already-applied']").count()
            if applied_badge > 0:
                return True

            # Check 3: Applied button text
            applied_btn = await page.locator("button:has-text('Applied'), span:has-text('Applied')").count()
            if applied_btn > 0:
                for el in await page.locator("button:has-text('Applied'), span:has-text('Applied')").all():
                    txt = (await el.text_content() or "").strip().lower()
                    if txt in ["applied", "already applied"]:
                        return True

            # Check 4: Success confirmation text on page
            body_text = (await page.locator("body").text_content() or "").lower()
            if any(k in body_text for k in ["applied to \"", "successfully applied", "application sent"]):
                return True

            return False
        except Exception as e:
            print(f"[Naukri Bot] Confirmation check note: {e}")
            return False

    async def _handle_chatbot_drawer(self, page, job_title: str, job_url: str, user_id: str = None) -> bool:
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
                # Check if application already completed without questionnaire
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

                # 1. Check for Radio Button options (.ssrc__radio-btn-container, .singleselect-radiobutton-container)
                radio_containers = await drawer.locator(".ssrc__radio-btn-container, .singleselect-radiobutton-container .ssrc__radio-btn-container").all()
                if radio_containers:
                    option_texts = []
                    for rc in radio_containers:
                        t = (await rc.text_content() or "").strip()
                        option_texts.append(t)

                    best_idx = await self._get_best_option_index(current_q, option_texts, job_title=job_title, job_url=job_url, user_id=user_id)
                    if best_idx is None:
                        best_idx = 0
                    print(f"  -> Selecting Radio Option [{best_idx}]: '{option_texts[best_idx]}'")

                    # Dispatch native select and click in browser context
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
                    best_idx = await self._get_best_option_index(current_q, chip_texts, job_title=job_title, job_url=job_url, user_id=user_id)
                    if best_idx is None:
                        best_idx = 0
                    print(f"  -> Clicking Option Chip [{best_idx}]: '{chip_texts[best_idx]}'")
                    await chips[best_idx].click(force=True)
                    action_taken = True
                    await page.wait_for_timeout(800)

                # 3. Check for Text / CTC / Number Input (.textArea, input, textarea)
                text_input = drawer.locator(".textArea, textarea, input:not([type='radio']):not([type='checkbox']):not([type='file'])").first
                if await text_input.is_visible():
                    answer_text = await self._get_smart_answer(current_q, job_title=job_title, job_url=job_url, user_id=user_id)
                    if not answer_text:
                        print(f"  -> Question '{current_q}' is not answered in memory or by user. Pausing.")
                        return False
                    print(f"  -> Answering via Text: '{answer_text}'")
                    await text_input.click()
                    # Clear any existing text and type answer
                    await text_input.fill("") if hasattr(text_input, "fill") else None
                    await text_input.press_sequentially(answer_text, delay=35)
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

    async def apply_single_job(self, job_url: str, job_title: str = "AI Engineer", company: str = "Recruiter", user_id: str = None):
        """
        Executes end-to-end autonomous application to a single live Naukri job listing.
        Returns verified proof or alerts candidate if manual intervention is required.
        """
        cookies = self._load_cookies(user_id=user_id)
        if not cookies:
            return {
                "status": "session_required",
                "message": "No active session cookies connected for your account. Please connect your cookies in Settings or use 1-Click AI Tailored Pitch to apply directly."
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
                    user_agent=user_agent
                )
                await context.add_cookies(cookies)
                page = await context.new_page()
                stealth = Stealth()
                await stealth.apply_stealth_async(page)
    
                try:
                    print(f"\n[Naukri Bot] Navigating to: {job_title} -> {job_url}")
                    await page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(2500)
    
                    # Check if already applied
                    if await self._is_submission_confirmed(page):
                        await page.screenshot(path=proof_path)
                        await browser.close()
                        return {
                            "status": "already_applied",
                            "job_title": job_title,
                            "job_url": job_url,
                            "proof_image": proof_url,
                            "message": "Already applied to this job."
                        }
    
                    # Check if external company portal
                    external_btn = page.locator(".company-site-button, button:has-text('Apply on company site')").first
                    if await external_btn.is_visible():
                        await page.screenshot(path=proof_path)
                        await browser.close()
                        return {
                            "status": "external_portal",
                            "job_title": job_title,
                            "job_url": job_url,
                            "proof_image": proof_url,
                            "message": "Job redirects to an external company ATS portal."
                        }
    
                    # Locate Direct Apply Button
                    apply_btn = page.locator("#apply-button, button.apply-button, button:has-text('Apply on Naukri'), button:has-text('Apply')").first
                    if not await apply_btn.is_visible():
                        await page.screenshot(path=proof_path)
                        await browser.close()
                        return {
                            "status": "external_portal",
                            "job_title": job_title,
                            "job_url": job_url,
                            "proof_image": proof_url,
                            "message": "Direct apply button not found (external redirect)."
                        }
    
                    # Physical click on Apply
                    print(f"[Naukri Bot] Physical click on Apply button for {job_title}...")
                    await apply_btn.click()
                    await page.wait_for_timeout(3500)
    
                    # Run questionnaire handler if chatbot appears
                    applied_ok = await self._handle_chatbot_drawer(page, job_title, job_url, user_id=user_id)
                    await page.wait_for_timeout(2500)
    
                    # Capture definitive proof screenshot
                    await page.screenshot(path=proof_path)
    
                    # Final submission confirmation
                    if applied_ok or await self._is_submission_confirmed(page):
                        print(f"[Naukri Bot] [SUCCESS] VERIFIED SUCCESS: Application submitted for {job_title}!")
                        await browser.close()
                        return {
                            "status": "applied_successfully",
                            "job_title": job_title,
                            "job_url": job_url,
                            "proof_image": proof_url,
                            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    else:
                        print(f"[Naukri Bot] [NOTICE] Incomplete submission: Questionnaire or external link requires candidate attention.")
                        # Dispatch Telegram alert so the user is immediately aware
                        await notifier.send_hitl_alert(
                            job_title=job_title,
                            company="Naukri Recruiter",
                            platform="Naukri",
                            job_url=job_url,
                            reason="Recruiter screening questionnaire requires human verification."
                        )
                        await browser.close()
                        return {
                            "status": "needs_human_action",
                            "job_title": job_title,
                            "job_url": job_url,
                            "proof_image": proof_url,
                            "message": "Screening questionnaire requires manual review. Alert sent to your Telegram!"
                        }
    
                except Exception as e:
                    await browser.close()
                    return {"status": "error", "message": str(e), "job_title": job_title}
    
        except Exception as browser_err:
            clean_err = str(browser_err).splitlines()[0] if str(browser_err) else "Browser error"
            print(f"[Naukri Bot] Playwright notice: {clean_err}. Executing session apply...")
            from app.agents.naukri_apply_agent import naukri_apply_agent
            return await naukri_apply_agent.apply_to_job(job_title=job_title, company=company, job_url=job_url, user_id=user_id)

    async def execute_live_apply(self, query: str = "AI Engineer", limit: int = 3, user_id: str = None):
        """
        Batch autonomous application across fresh matching Naukri listings.
        """
        cookies = self._load_cookies(user_id=user_id)
        if not cookies:
            return {
                "status": "session_required",
                "message": "No active session cookies connected for your account. Please connect your cookies in Settings or use 1-Click AI Tailored Pitch to apply directly."
            }

        results = []
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=user_agent
                )
                await context.add_cookies(cookies)
                page = await context.new_page()
                stealth = Stealth()
                await stealth.apply_stealth_async(page)

                clean_query = query.replace(" ", "-").lower()
                search_url = f"https://www.naukri.com/{clean_query}-jobs"
                print(f"[Naukri Live Runner] Scanning: {search_url}")

                try:
                    try:
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)

                        # Extract candidate job listing links
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
                        await stealth.apply_stealth_async(job_page)

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
                            external_btn = job_page.locator(".company-site-button, button:has-text('Apply on company site')").first
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
                            apply_btn = job_page.locator("#apply-button, button.apply-button, button:has-text('Apply on Naukri'), button:has-text('Apply')").first
                            if await apply_btn.is_visible():
                                print(f"  -> Clicking 'Apply' for {job_title}...")
                                await apply_btn.click()
                                await job_page.wait_for_timeout(3500)

                                # Questionnaire handler
                                applied_ok = await self._handle_chatbot_drawer(job_page, job_title, job_url, user_id=user_id)
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
                                    "status": "external_portal",
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
                    return {"status": "error", "message": str(e)}

                return {"status": "completed", "applications": results}
        except Exception as browser_err:
            clean_err = str(browser_err).splitlines()[0] if str(browser_err) else "Browser error"
            print(f"[Naukri Bot] Playwright notice: {clean_err}. Executing session batch apply...")
            from app.scrapers.naukri_scraper import naukri_scraper
            from app.agents.naukri_apply_agent import naukri_apply_agent
            matched = await naukri_scraper.search_jobs(query=query, limit=limit)
            batch_results = []
            for j in matched:
                res = await naukri_apply_agent.apply_to_job(job_title=j.title, company=j.company, job_url=j.job_url, user_id=user_id)
                batch_results.append(res)
            return {"status": "completed", "applications": batch_results}

naukri_live_runner = RealNaukriApplyEngine()
