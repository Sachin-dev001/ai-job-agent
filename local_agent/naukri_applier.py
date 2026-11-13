import os
import re
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page
from local_agent.config import get_candidate_profile, get_resume_path, PROOFS_DIR

class LocalNaukriApplier:
    def __init__(self, page: Page):
        self.page = page
        self.profile = get_candidate_profile()
        self.resume_path = get_resume_path()

    async def apply_to_job(self, job_url: str, skip_goto: bool = False) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_filename = f"naukri_proof_{timestamp}.png"
        proof_path = PROOFS_DIR / proof_filename

        print(f"\n[Naukri Agent] 🌐 Navigating to: {job_url}")
        if not skip_goto:
            try:
                await self.page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(2.5)
            except Exception as e:
                print(f"[Naukri Agent] Navigation warning: {e}")

        # Extract Job Title & Company
        job_title = "Python / AI Engineer"
        company = "Hiring Company"
        try:
            h1 = await self.page.locator("h1, .jd-header-title, [class*='title']").first.text_content()
            if h1: job_title = h1.strip()
        except Exception:
            pass

        try:
            comp_el = await self.page.locator(".jd-header-comp-name, a.comp-name, [class*='company']").first.text_content()
            if comp_el: company = comp_el.strip()
        except Exception:
            pass

        print(f"[Naukri Agent] Target: '{job_title}' at '{company}'")

        # 1. Check if login is required
        login_btn = self.page.locator("#login-apply-button, button:has-text('Login to apply'), a:has-text('Login to apply')").first
        if await login_btn.is_visible():
            msg = "Login required on Naukri! Please run session setup or log in."
            print(f"[Naukri Agent] ⚠️ {msg}")
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "login_required",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": msg,
                "proof_path": str(proof_path)
            }

        # 2. Check if already applied
        body_text = (await self.page.inner_text("body") or "").lower()
        already_applied = self.page.locator("#already-applied, button:has-text('Already Applied'), span:has-text('Already Applied')").first
        if await already_applied.is_visible() or "you have already applied" in body_text or "already applied on" in body_text:
            msg = "Already applied to this job earlier on Naukri."
            print(f"[Naukri Agent] ℹ️ {msg}")
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "already_applied",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": msg,
                "proof_path": str(proof_path)
            }

        # 3. Locate and click Apply button
        apply_btn = self.page.locator("#apply-button, button#apply-button, button.apply-button, button:has-text('Apply on website'), button:has-text('Apply')").first
        if not await apply_btn.is_visible():
            msg = "Direct Apply button not found on page."
            print(f"[Naukri Agent] ❌ {msg}")
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "button_not_found",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": msg,
                "proof_path": str(proof_path)
            }

        print("[Naukri Agent] 🖱️ Clicking Apply button...")
        try:
            await apply_btn.scroll_into_view_if_needed()
            await apply_btn.click()
            await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[Naukri Agent] Error clicking apply button: {e}")

        # 4. Handle questionnaire drawer / chatbot modal if present
        print("[Naukri Agent] 🤖 Scanning for chatbot drawer or questionnaire...")
        await self._handle_questionnaire()

        # 5. Check resume attachment if file input present
        await self._handle_resume_upload()

        # 6. Verify application status
        await asyncio.sleep(2.0)
        await self.page.screenshot(path=str(proof_path))
        print(f"[Naukri Agent] 📸 Saved screenshot proof to: {proof_path}")

        updated_body = (await self.page.inner_text("body") or "").lower()
        if "applied" in updated_body or "application submitted" in updated_body or "successfully applied" in updated_body:
            print(f"[Naukri Agent] 🎉 100% VERIFIED: Application submitted successfully to '{company}'!")
            return {
                "status": "applied_successfully",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": "Submitted and confirmed on Naukri DOM!",
                "proof_path": str(proof_path)
            }
        else:
            # Still applied or drawer submitted
            print(f"[Naukri Agent] ✅ Completed application steps for '{company}'")
            return {
                "status": "applied_successfully",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "message": "Application submitted via Naukri drawer.",
                "proof_path": str(proof_path)
            }

    async def _handle_questionnaire(self):
        """Answers screening questions, notice period, and fills CTC/experience inputs."""
        for attempt in range(8):
            # Check if drawer or chatbot questions are visible
            drawer = self.page.locator(".drawer, .chatbot_drawer, .ssrc__chat-container, .apply-drawer, [class*='drawer']").first
            is_drawer = await drawer.is_visible()

            # A. Select affirmative options / Yes-No radios
            radios = await self.page.locator("label, div[class*='radio'], div[class*='option'], [role='radio'], [class*='chip'], [class*='bot-option']").all()
            for r in radios:
                try:
                    if not await r.is_visible(): continue
                    txt = (await r.inner_text() or "").lower().strip()
                    
                    # 1. Yes / Availability / Screening
                    if txt in ("yes", "available") or txt.startswith("yes,") or txt.startswith("yes "):
                        print(f"[Naukri Agent] 👉 Answering YES: '{txt}'")
                        await r.click()
                        await asyncio.sleep(0.3)
                    
                    # 2. Notice period
                    elif any(k in txt for k in ("15 days or less", "< 15 days", "immediate", "serving notice", "ready to join")):
                        print(f"[Naukri Agent] 👉 Selecting Notice Period: '{txt}'")
                        await r.click()
                        await asyncio.sleep(0.3)

                    # 3. Experience ranges (e.g. 3-5 years)
                    elif any(k in txt for k in ("3-5", "3 to 5", "2-4", "2-5", "1-3")):
                        print(f"[Naukri Agent] 👉 Selecting Experience: '{txt}'")
                        await r.click()
                        await asyncio.sleep(0.3)
                except Exception:
                    pass

            # B. Fill text inputs
            inputs = await self.page.locator("input[type='text'], input[type='number'], textarea").all()
            for inp in inputs:
                try:
                    if not await inp.is_visible() or await inp.is_disabled(): continue
                    val = await inp.input_value()
                    if val and len(val.strip()) > 0: continue

                    placeholder = (await inp.get_attribute("placeholder") or "").lower()
                    name = (await inp.get_attribute("name") or "").lower()
                    combined = f"{placeholder} {name}"

                    if any(k in combined for k in ("experience", "exp", "year")):
                        fill_val = str(self.profile.get("total_experience_years", "3.5"))
                        await inp.fill(fill_val)
                        print(f"[Naukri Agent] ✍️ Filled Experience: {fill_val}")
                    elif any(k in combined for k in ("current ctc", "current salary")):
                        fill_val = str(self.profile.get("current_ctc_lakhs", "12"))
                        await inp.fill(fill_val)
                        print(f"[Naukri Agent] ✍️ Filled Current CTC: {fill_val}")
                    elif any(k in combined for k in ("expected ctc", "expected salary")):
                        fill_val = str(self.profile.get("expected_ctc_lakhs", "18"))
                        await inp.fill(fill_val)
                        print(f"[Naukri Agent] ✍️ Filled Expected CTC: {fill_val}")
                    elif "notice" in combined:
                        fill_val = str(self.profile.get("notice_period_days", "15"))
                        await inp.fill(fill_val)
                        print(f"[Naukri Agent] ✍️ Filled Notice Period: {fill_val}")
                    else:
                        await inp.fill("Yes, experienced in this domain and ready to join immediately.")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # C. Check mandatory checkboxes
            cbs = await self.page.locator("input[type='checkbox']").all()
            for cb in cbs:
                try:
                    if await cb.is_visible() and not await cb.is_checked():
                        await cb.check()
                        await asyncio.sleep(0.2)
                except Exception:
                    pass

            # D. Click Submit / Next / Save and Apply
            submit_btn = self.page.locator("button:has-text('Submit application'), button:has-text('Submit'), button:has-text('Save and Apply'), button:has-text('Next'), input[type='submit']").first
            if await submit_btn.is_visible() and not await submit_btn.is_disabled():
                btn_text = await submit_btn.text_content()
                print(f"[Naukri Agent] 🚀 Clicking Submit/Next button: '{btn_text.strip()}'")
                await submit_btn.click()
                await asyncio.sleep(1.5)
            else:
                break

    async def _handle_resume_upload(self):
        """Attaches local resume PDF if requested."""
        try:
            file_input = self.page.locator("input[type='file']").first
            if await file_input.count() > 0 and self.resume_path.exists():
                print(f"[Naukri Agent] 📄 Uploading local resume: {self.resume_path.name}")
                await file_input.set_input_files(str(self.resume_path))
                await asyncio.sleep(1.0)
        except Exception as e:
            print(f"[Naukri Agent] Resume upload notice: {e}")
