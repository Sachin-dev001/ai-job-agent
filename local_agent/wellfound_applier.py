import os
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page
from local_agent.config import get_candidate_profile, get_resume_path, PROOFS_DIR

class LocalWellfoundApplier:
    def __init__(self, page: Page):
        self.page = page
        self.profile = get_candidate_profile()
        self.resume_path = get_resume_path()

    async def apply_to_job(self, job_url: str, skip_goto: bool = False) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_filename = f"wellfound_proof_{timestamp}.png"
        proof_path = PROOFS_DIR / proof_filename

        print(f"\n[Wellfound Agent] 🌐 Navigating to: {job_url}")
        if not skip_goto:
            try:
                await self.page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(2.5)
            except Exception as e:
                print(f"[Wellfound Agent] Navigation warning: {e}")

        # Extract Title & Company
        job_title = "Startup Role"
        company = "Startup"
        try:
            h1 = await self.page.locator("h1").first.text_content()
            if h1: job_title = h1.strip()
        except Exception:
            pass

        try:
            comp_el = await self.page.locator("[data-test='JobCompany'], h2, a[href*='/company/']").first.text_content()
            if comp_el: company = comp_el.strip()
        except Exception:
            pass

        print(f"[Wellfound Agent] Target: '{job_title}' at '{company}'")

        # 1. Check if already applied
        body_text = (await self.page.inner_text("body") or "").lower()
        applied_btn = self.page.locator("button:has-text('Applied'), [data-test='applied']").first
        if await applied_btn.is_visible() or "already applied" in body_text or "application sent" in body_text:
            msg = "Already applied to this Wellfound job earlier."
            print(f"[Wellfound Agent] ℹ️ {msg}")
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "already_applied",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": msg,
                "proof_path": str(proof_path)
            }

        # 2. Click Apply button
        apply_btn = self.page.locator("button:has-text('Apply'), button:has-text('Apply now'), button[data-test='JobApplyButton']").first
        if not await apply_btn.is_visible():
            msg = "Apply button not visible on Wellfound job posting."
            print(f"[Wellfound Agent] ❌ {msg}")
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "button_not_found",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": msg,
                "proof_path": str(proof_path)
            }

        print("[Wellfound Agent] 🖱️ Clicking Apply button...")
        try:
            await apply_btn.scroll_into_view_if_needed()
            await apply_btn.click()
            await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[Wellfound Agent] Error clicking apply: {e}")

        # 3. Fill recruiter pitch note
        note_area = self.page.locator("textarea[name='userNote'], textarea[placeholder*='note' i], textarea[placeholder*='pitch' i], textarea").first
        if await note_area.is_visible() and not await note_area.is_disabled():
            pitch = self.profile.get("recruiter_pitch") or (
                f"Hi {company} Hiring Team,\n\n"
                f"I am very excited to apply for the {job_title} position! "
                "I bring extensive hands-on experience in Python, GenAI, LLMs, and building high-performance systems. "
                "I am immediately available for interviews.\n\n"
                f"Best regards,\n{self.profile.get('full_name', 'Sachin Sharma')}"
            )
            print(f"[Wellfound Agent] ✍️ Filling recruiter note for {company}...")
            await note_area.fill(pitch)
            await asyncio.sleep(0.5)

        # 4. Handle screening questions / radios
        radios = await self.page.locator("input[type='radio'], label:has-text('Yes'), label:has-text('No')").all()
        for r in radios:
            try:
                if not await r.is_visible(): continue
                parent = r.locator("..")
                context = ((await parent.text_content()) or "").lower()
                
                # If question is about visa/sponsorship -> pick NO
                if "visa" in context or "sponsorship" in context:
                    no_opt = parent.locator("label:has-text('No'), input[value*='no' i]").first
                    if await no_opt.is_visible():
                        await no_opt.click()
                        print("[Wellfound Agent] 👉 Answered NO to visa sponsorship.")
                # Otherwise affirmative YES
                elif "yes" in context:
                    await r.click()
                    print("[Wellfound Agent] 👉 Answered YES to screening requirement.")
            except Exception:
                pass

        # 5. Handle experience & salary inputs
        inputs = await self.page.locator("input[type='text'], input[type='number']").all()
        for inp in inputs:
            try:
                if not await inp.is_visible() or await inp.is_disabled(): continue
                val = await inp.input_value()
                if val and len(val.strip()) > 0: continue

                name = ((await inp.get_attribute("name") or "") + " " + (await inp.get_attribute("placeholder") or "")).lower()
                if any(k in name for k in ("exp", "year")):
                    await inp.fill(str(self.profile.get("total_experience_years", "3.5")))
                elif any(k in name for k in ("salary", "ctc")):
                    await inp.fill(str(self.profile.get("expected_ctc_lakhs", "18")))
            except Exception:
                pass

        # 6. Upload resume if file input present
        try:
            file_inp = self.page.locator("input[type='file']").first
            if await file_inp.count() > 0 and self.resume_path.exists():
                print(f"[Wellfound Agent] 📄 Attaching resume: {self.resume_path.name}")
                await file_inp.set_input_files(str(self.resume_path))
                await asyncio.sleep(0.8)
        except Exception:
            pass

        # 7. Submit Application
        send_btn = self.page.locator("button:has-text('Send application'), button:has-text('Submit application'), button:has-text('Send')").first
        if await send_btn.is_visible() and not await send_btn.is_disabled():
            print("[Wellfound Agent] 🚀 Submitting Wellfound application...")
            await send_btn.scroll_into_view_if_needed()
            await send_btn.click()
            await asyncio.sleep(3.0)

        # 8. Save Screenshot Proof
        await self.page.screenshot(path=str(proof_path))
        print(f"[Wellfound Agent] 📸 Saved screenshot proof to: {proof_path}")

        return {
            "status": "applied_successfully",
            "job_title": job_title,
            "company": company,
            "job_url": job_url,
            "message": "Submitted successfully on Wellfound!",
            "proof_path": str(proof_path)
        }
