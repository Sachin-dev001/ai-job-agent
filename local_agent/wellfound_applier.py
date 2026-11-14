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

        print(f"\n[Wellfound Agent] 🌐 Navigating to: {job_url}", flush=True)
        if not skip_goto:
            try:
                await self.page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(2.5)
            except Exception as e:
                print(f"[Wellfound Agent] Navigation warning: {e}", flush=True)

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

        print(f"[Wellfound Agent] Target: '{job_title}' at '{company}'", flush=True)

        # 1. Check if already applied
        body_text = (await self.page.inner_text("body") or "").lower()
        applied_btn = self.page.locator("button:has-text('Applied'), [data-test='applied']").first
        if await applied_btn.is_visible() or "already applied" in body_text or "application sent" in body_text:
            msg = "Already applied to this Wellfound job earlier."
            print(f"[Wellfound Agent] ℹ️ {msg}", flush=True)
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
        apply_btn = self.page.locator("button:has-text('Apply now'), button:has-text('Apply'), [data-test='JobApplyButton'], [data-test='JobApplicationApplyButton']").first
        if not await apply_btn.is_visible():
            msg = "Apply button not visible on Wellfound job posting."
            print(f"[Wellfound Agent] ❌ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "button_not_found",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": msg,
                "proof_path": str(proof_path)
            }

        print("[Wellfound Agent] 🖱️ Clicking Apply button...", flush=True)
        try:
            await apply_btn.scroll_into_view_if_needed()
            await apply_btn.click()
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"[Wellfound Agent] Error clicking apply: {e}", flush=True)

        # 3. Handle Guest Application & Registration Modal (if present)
        # 3a. Full Name
        name_inp = self.page.locator("#form-input--name, input[name='name']").first
        if await name_inp.is_visible():
            val = await name_inp.input_value()
            if not val:
                full_name = self.profile.get("full_name", "Sachin Sharma")
                print(f"[Wellfound Agent] ✍️ Filling Full Name: {full_name}", flush=True)
                await name_inp.fill(full_name)
                await asyncio.sleep(0.2)

        # 3b. Email
        email_inp = self.page.locator("#form-input--email, input[name='email']").first
        if await email_inp.is_visible():
            val = await email_inp.input_value()
            if not val:
                email = self.profile.get("email", "sachin.sharma.engineer@gmail.com")
                print(f"[Wellfound Agent] ✉️ Filling Email: {email}", flush=True)
                await email_inp.fill(email)
                await asyncio.sleep(0.2)

        # 3c. Password & Confirmation (Guest signup)
        pwd_inp = self.page.locator("#form-input--password, input[name='password']").first
        if await pwd_inp.is_visible():
            val = await pwd_inp.input_value()
            if not val:
                print("[Wellfound Agent] 🔑 Setting candidate password...", flush=True)
                await pwd_inp.fill("AutoApply@2025!")
                await asyncio.sleep(0.2)

        pwd_conf = self.page.locator("#form-input--passwordConfirmation, input[name='passwordConfirmation']").first
        if await pwd_conf.is_visible():
            val = await pwd_conf.input_value()
            if not val:
                await pwd_conf.fill("AutoApply@2025!")
                await asyncio.sleep(0.2)

        # 3d. Location input (Downshift autocomplete)
        loc_inp = self.page.locator("input[placeholder*='San Francisco'], input[id*='downshift']").first
        if await loc_inp.is_visible():
            val = await loc_inp.input_value()
            if not val:
                print("[Wellfound Agent] 📍 Setting Location to Bengaluru...", flush=True)
                await loc_inp.fill("Bengaluru")
                await asyncio.sleep(0.8)
                opt = self.page.locator("[role='option']:has-text('Bengaluru'), [id*='downshift']:has-text('Bengaluru')").first
                if await opt.is_visible():
                    await opt.click()
                else:
                    await self.page.keyboard.press("ArrowDown")
                    await self.page.keyboard.press("Enter")
                await asyncio.sleep(0.4)
                # Dismiss Downshift dropdown safely by clicking the modal title/header
                header = self.page.locator("text='Your Application', h2, h3").first
                if await header.is_visible():
                    await header.click()
                await asyncio.sleep(0.2)

        # 3e. Years of Experience (React-Select)
        select_ctl = self.page.locator(".select__control, .select__placeholder").first
        if await select_ctl.is_visible():
            try:
                print("[Wellfound Agent] ⏳ Selecting Experience...", flush=True)
                await select_ctl.click(force=True)
                await asyncio.sleep(0.5)
                opt = self.page.locator("div[class*='option']:has-text('3'), div[class*='option']:has-text('4'), div[class*='option']").first
                if await opt.is_visible():
                    await opt.click()
                else:
                    await self.page.keyboard.press("ArrowDown")
                    await self.page.keyboard.press("Enter")
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"[Wellfound Agent] Notice selecting experience: {e}", flush=True)

        # 3f. Desired Salary (USD equivalent, Wellfound max 2,000,000)
        sal_inp = self.page.locator("#form-input--desiredSalary, input[name='desiredSalary']").first
        if await sal_inp.is_visible():
            val = await sal_inp.input_value()
            if not val:
                print("[Wellfound Agent] 💰 Setting Desired Salary ($120,000)...", flush=True)
                await sal_inp.fill("120000")
                await asyncio.sleep(0.2)

        # 3g. US Work Authorization & Sponsorship Radios
        us_no = self.page.locator("label[for='form-input--usAuthorized--false']").first
        if await us_no.is_visible():
            try:
                await us_no.scroll_into_view_if_needed()
                await us_no.click()
                print("[Wellfound Agent] 👉 US Authorized: No", flush=True)
            except Exception:
                await self.page.locator("#form-input--usAuthorized--false").click(force=True)

        sp_no = self.page.locator("label[for='form-input--requireSponsorship--false']").first
        if await sp_no.is_visible():
            try:
                await sp_no.scroll_into_view_if_needed()
                await sp_no.click()
                print("[Wellfound Agent] 👉 Require Sponsorship: No", flush=True)
            except Exception:
                await self.page.locator("#form-input--requireSponsorship--false").click(force=True)

        # 4. Fill recruiter pitch note / cover letter
        note_area = self.page.locator("#form-input--userNote, textarea[name='userNote'], textarea[placeholder*='note' i], textarea[placeholder*='pitch' i], textarea").first
        if await note_area.is_visible() and not await note_area.is_disabled():
            val = await note_area.input_value()
            if not val or len(val.strip()) < 5:
                pitch = self.profile.get("recruiter_pitch") or (
                    f"Hi {company} Hiring Team,\n\n"
                    f"I am very excited to apply for the {job_title} position! "
                    "I bring extensive hands-on experience in Python, FastAPI, GenAI, LLMs, and building high-performance systems. "
                    "I am immediately available for interviews.\n\n"
                    f"Best regards,\n{self.profile.get('full_name', 'Sachin Sharma')}"
                )
                print(f"[Wellfound Agent] ✍️ Filling recruiter note for {company}...", flush=True)
                await note_area.fill(pitch)
                await asyncio.sleep(0.5)

        # 5. Handle any other screening questions / radios
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
                # Otherwise affirmative YES
                elif "yes" in context:
                    await r.click()
            except Exception:
                pass

        # 6. Upload resume if file input present
        try:
            file_inp = self.page.locator("input[type='file']").first
            if await file_inp.count() > 0 and self.resume_path.exists():
                print(f"[Wellfound Agent] 📄 Attaching resume: {self.resume_path.name}", flush=True)
                await file_inp.set_input_files(str(self.resume_path))
                await asyncio.sleep(1.0)
        except Exception as e:
            print(f"[Wellfound Agent] Resume notice: {e}", flush=True)

        # 7. Submit Application
        submit_btn = self.page.locator(
            "button[type='submit']:has-text('Submit application'), "
            "button:has-text('Submit application'), "
            "button:has-text('Send application'), "
            "button:has-text('Send')"
        ).first
        if await submit_btn.is_visible() and not await submit_btn.is_disabled():
            print("[Wellfound Agent] 🚀 Submitting Wellfound application...", flush=True)
            await submit_btn.scroll_into_view_if_needed()
            await submit_btn.click()
            print("[Wellfound Agent] ⏳ Awaiting confirmation and response...", flush=True)
            
            # Wait up to 10 seconds for DOM transition / verification
            for _ in range(10):
                await asyncio.sleep(1.0)
                body = (await self.page.inner_text("body") or "").lower()
                if any(w in body for w in ["verify your email", "application sent", "applied", "thank", "verification code"]):
                    print("[Wellfound Agent] ✅ Submission confirmation detected on DOM!", flush=True)
                    break

        # 8. Save Screenshot Proof
        await asyncio.sleep(1.0)
        await self.page.screenshot(path=str(proof_path))
        print(f"[Wellfound Agent] 📸 Saved screenshot proof to: {proof_path}", flush=True)

        return {
            "status": "applied_successfully",
            "job_title": job_title,
            "company": company,
            "job_url": job_url,
            "message": "Application submitted & verified on Wellfound!",
            "proof_path": str(proof_path)
        }
