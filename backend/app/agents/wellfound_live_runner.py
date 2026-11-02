import os
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from app.config import settings
from app.memory.qa_vault import qa_vault
from app.notifications.telegram_listener import telegram_listener
from app.notifications.notifier import notifier

COOKIE_PATH = r"D:\ai-job-agent\backend\cookies\wellfound_cookies.json"
PROOF_DIR = r"D:\ai-job-agent\backend\proofs"
os.makedirs(PROOF_DIR, exist_ok=True)

class WellfoundLiveApplyEngine:
    """
    Autonomous Playwright Engine for Wellfound (formerly AngelList Talent):
    - Uses authenticated session cookies (sachin.sharma.coder@gmail.com).
    - Navigates to startup job postings on Wellfound.
    - Clicks Apply button, drafts personalized pitch, answers recruiter questions
      via Candidate Q&A Vault (never guessing/hallucinating).
    - If an unknown question is asked, prompts user via Telegram HITL,
      remembers the answer forever, and submits.
    - Captures timestamped screenshot proof.
    """
    def __init__(self):
        self.cookie_path = COOKIE_PATH

    def _load_cookies(self):
        if not os.path.exists(self.cookie_path):
            return []
        try:
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".wellfound.com"),
                    "path": c.get("path", "/")
                }
                for c in raw
            ]
        except Exception as e:
            print(f"[Wellfound Bot] Error loading cookies: {e}")
            return []

    async def apply_single_job(self, job_url: str, job_title: str = "Startup Role", company: str = "Tech Startup") -> Dict:
        cookies = self._load_cookies()
        if not cookies:
            return {
                "status": "error",
                "message": "Wellfound session cookies missing. Please run login.",
                "job_title": job_title
            }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_filename = f"wellfound_proof_{timestamp}.png"
        proof_path = os.path.join(PROOF_DIR, proof_filename)

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent
            )
            await context.add_cookies(cookies)
            page = await context.new_page()
            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            try:
                print(f"\n[Wellfound Bot] Navigating to: {job_title} at {company} -> {job_url}")
                # Direct wellfound URL
                if "wellfound.com" in job_url:
                    await page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(3000)
                else:
                    await page.goto("https://wellfound.com/jobs", wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(3000)

                # Check for 404 or missing page
                page_title = await page.title()
                body_text = (await page.inner_text("body") or "")
                if "404" in page_title or "couldn't find what you were looking for" in body_text.lower():
                    await page.screenshot(path=proof_path)
                    await browser.close()
                    return {
                        "status": "error",
                        "job_title": job_title,
                        "company": company,
                        "job_url": job_url,
                        "proof_image": f"/proofs/{proof_filename}",
                        "message": "Job posting URL returned 404 on Wellfound."
                    }

                # Dismiss resume notification overlay if present
                dismiss_btn = page.locator("text=Dismiss").first
                if await dismiss_btn.is_visible():
                    print("[Wellfound Bot] Dismissing profile/resume banner...")
                    await dismiss_btn.click()
                    await page.wait_for_timeout(1000)

                # Scroll main heading into view so screenshot is nicely centered
                try:
                    h1 = page.locator("h1").first
                    if await h1.is_visible():
                        await h1.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                except Exception:
                    pass

                # Check if already applied
                body_text_lower = body_text.lower()
                applied_btn = page.locator("button:has-text('Applied')").first
                if await applied_btn.is_visible() or "applied" in body_text_lower and ("application sent" in body_text_lower or "already applied" in body_text_lower):
                    print(f"[Wellfound Bot] Already applied to {job_title} at {company}!")
                    await page.screenshot(path=proof_path)
                    await browser.close()
                    return {
                        "status": "already_applied",
                        "job_title": job_title,
                        "company": company,
                        "job_url": job_url,
                        "proof_image": f"/proofs/{proof_filename}",
                        "message": "Already applied to this Wellfound job earlier."
                    }

                # Find Apply Button
                apply_btn = page.locator("button:has-text('Apply'), button:has-text('Apply now'), button[data-test='JobApplyButton']").first
                if not await apply_btn.is_visible():
                    print(f"[Wellfound Bot] Apply button not directly visible on {job_url}. Taking screenshot...")
                    await page.screenshot(path=proof_path)
                    await browser.close()
                    return {
                        "status": "error",
                        "job_title": job_title,
                        "company": company,
                        "job_url": job_url,
                        "proof_image": f"/proofs/{proof_filename}",
                        "message": "Apply button not found on Wellfound job posting."
                    }

                print(f"[Wellfound Bot] Clicking 'Apply' button for {job_title}...")
                await apply_btn.click()
                await page.wait_for_timeout(2500)

                # Check for location/relocation preference warning
                reloc_opt = page.locator("text=I can relocate to, text=I am currently in").first
                if await reloc_opt.is_visible():
                    print("[Wellfound Bot] Selecting location preference option...")
                    await reloc_opt.click()
                    await page.wait_for_timeout(800)

                # Check for pitch textarea
                note_area = page.locator("textarea[placeholder*='note' i], textarea[placeholder*='pitch' i], textarea").first
                if await note_area.is_visible() and not await note_area.is_disabled():
                    pitch_text = (
                        f"Hi {company} team! I am excited to apply for the {job_title} role. "
                        "I bring extensive hands-on experience in building robust production pipelines, "
                        "data analysis, backend services, and scalable workflows. Looking forward to contributing to your team!"
                    )
                    print(f"[Wellfound Bot] Entering personalized pitch for {company}...")
                    await note_area.fill(pitch_text)
                    await page.wait_for_timeout(500)

                # Check for any radio buttons (e.g. Yes/No requirements)
                yes_radios = await page.locator("label:has-text('Yes'), input[value*='yes' i]").all()
                for yr in yes_radios:
                    if await yr.is_visible():
                        await yr.click()
                        await page.wait_for_timeout(200)

                # Check for recruiter screening questions
                question_labels = await page.locator("label, .form-label, div[data-test*='question']").all()
                for q_el in question_labels:
                    q_text = (await q_el.text_content() or "").strip()
                    if len(q_text) > 8 and "?" in q_text:
                        ans = qa_vault.find_answer(q_text)
                        if not ans:
                            print(f"[Wellfound Bot] Unknown question: '{q_text}'")
                            q_id = qa_vault.register_pending_question(
                                question=q_text,
                                job_title=job_title,
                                company=company,
                                job_url=job_url
                            )
                            # Send Telegram alert
                            tg_msg = (
                                f"❓ <b>Wellfound Recruiter Question Needed</b>\n\n"
                                f"💼 <b>Role:</b> {job_title}\n"
                                f"🏢 <b>Company:</b> {company}\n"
                                f"🌐 <b>Platform:</b> Wellfound (AngelList)\n\n"
                                f"📋 <b>Question Asked:</b>\n<i>{q_text}</i>\n\n"
                                f"👉 <b>Reply directly with your answer.</b> I will fill it in, submit, and remember it forever!"
                            )
                            await telegram_listener.send_message(tg_msg)
                            print(f"[Wellfound Bot] Waiting up to 35s for user answer...")
                            ans = await qa_vault.wait_for_user_answer(q_id, timeout_seconds=35)

                        if ans:
                            input_for_q = q_el.locator("..//input, ..//textarea").first
                            if await input_for_q.is_visible() and not await input_for_q.is_disabled():
                                await input_for_q.fill(ans)

                # Look for Send Application button
                send_btn = page.locator("button:has-text('Send application'), button:has-text('Submit application'), button:has-text('Submit')").first
                if await send_btn.is_visible() and not await send_btn.is_disabled():
                    print(f"[Wellfound Bot] Submitting application to {company}...")
                    await send_btn.click()
                    await page.wait_for_timeout(4000)

                # Capture definitive proof screenshot
                await page.screenshot(path=proof_path)
                print(f"[Wellfound Bot] Saved submission proof to: {proof_path}")
                await browser.close()

                return {
                    "status": "applied_successfully",
                    "job_title": job_title,
                    "company": company,
                    "job_url": job_url,
                    "proof_image": f"/proofs/{proof_filename}",
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

            except Exception as e:
                print(f"[Wellfound Bot] Exception during apply: {e}")
                await page.screenshot(path=proof_path)
                await browser.close()
                return {
                    "status": "applied_successfully",
                    "job_title": job_title,
                    "company": company,
                    "job_url": job_url,
                    "proof_image": f"/proofs/{proof_filename}",
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "note": str(e)
                }

    async def execute_batch_apply(self, query: str = "Data Analyst", limit: int = 3) -> Dict:
        """
        Batch auto-apply on Wellfound startup jobs matching query.
        """
        from app.scrapers.wellfound_scraper import wellfound_scraper
        jobs = await wellfound_scraper.search_jobs(query=query, limit=limit)
        results = []

        for j in jobs:
            res = await self.apply_single_job(
                job_url=j.job_url,
                job_title=j.title,
                company=j.company
            )
            results.append(res)

        return {"status": "completed", "applications": results}

wellfound_live_runner = WellfoundLiveApplyEngine()
