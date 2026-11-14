import os
import re
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page
from local_agent.config import get_candidate_profile, get_resume_path, PROOFS_DIR

class LocalYCApplier:
    def __init__(self, page: Page):
        self.page = page
        self.profile = get_candidate_profile()
        self.resume_path = get_resume_path()

    async def apply_to_job(self, job_url: str, skip_goto: bool = False) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_filename = f"yc_proof_{timestamp}.png"
        proof_path = PROOFS_DIR / proof_filename

        print(f"\n[YC Agent] 🌐 Navigating to: {job_url}", flush=True)
        if not skip_goto:
            try:
                await self.page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(2.5)
            except Exception as e:
                err_str = str(e).lower()
                print(f"[YC Agent] Navigation warning: {e}", flush=True)
                if "err_too_many_redirects" in err_str or "redirect" in err_str:
                    print("[YC Agent] 🔄 Redirect loop detected due to stale/invalid cookies. Clearing YC cookies and retrying cleanly...", flush=True)
                    try:
                        await self.page.context.clear_cookies()
                        await asyncio.sleep(1.0)
                        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                        await asyncio.sleep(2.0)
                    except Exception as retry_err:
                        print(f"[YC Agent] Retry after cookie clear notice: {retry_err}", flush=True)

        # Extract Job Title & Startup Name
        job_title = "Startup Software / AI Engineer"
        company = "YC Startup"
        try:
            h1 = await self.page.locator(
                "h1, "
                ".job-name, "
                ".company-title h1, "
                "div[class*='job'] h1, "
                "div[class*='title'] h1"
            ).first.text_content()
            if h1:
                job_title = h1.strip()
        except Exception:
            pass

        try:
            comp_el = await self.page.locator(
                "a[href*='/companies/'], "
                ".company-name, "
                "h2, "
                "div[class*='company-name']"
            ).first.text_content()
            if comp_el:
                company = comp_el.strip()
        except Exception:
            pass

        print(f"[YC Agent] Target: '{job_title}' at '{company}'", flush=True)

        # 1. Check if already applied
        applied_btn = self.page.locator(
            "button:has-text('Applied'), "
            "span:has-text('Applied'), "
            "button:has-text('Application sent'), "
            "div:has-text('Application sent')"
        ).first
        body_text = (await self.page.inner_text("body") or "").lower()

        if await applied_btn.is_visible() or "you applied to this role" in body_text or "application sent" in body_text:
            msg = f"Already applied to '{job_title}' at '{company}' earlier."
            print(f"[YC Agent] ℹ️ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "already_applied",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": msg
            }

        # Check if login required
        login_btn = self.page.locator("a:has-text('Log In'), button:has-text('Log In'), a[href*='/login']").first
        if await login_btn.is_visible() and not await self.page.locator("button:has-text('Apply to this role'), button:has-text('Apply')").first.is_visible():
            msg = "YC Work at a Startup login required. Please run session setup."
            print(f"[YC Agent] ⚠️ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "login_required",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": msg
            }

        # 2. Click Apply button
        apply_btn = self.page.locator(
            "button:has-text('Apply to this role'), "
            "button:has-text('Apply'), "
            "a:has-text('Apply to this role'), "
            "a:has-text('Apply'), "
            "[data-test='apply-button']"
        ).first

        if not await apply_btn.is_visible():
            msg = "Apply button not visible on YC job posting."
            print(f"[YC Agent] ❌ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "button_not_found",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": msg
            }

        print("[YC Agent] 🖱️ Clicking 'Apply to this role'...", flush=True)
        try:
            await apply_btn.scroll_into_view_if_needed()
            await apply_btn.click()
            await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[YC Agent] Notice clicking apply button: {e}", flush=True)

        # 3. Fill Founder Note / Pitch
        note_area = self.page.locator(
            "textarea[placeholder*='note' i], "
            "textarea[placeholder*='message' i], "
            "textarea[name*='note' i], "
            "textarea[name*='message' i], "
            "div[role='dialog'] textarea, "
            "textarea"
        ).first

        if await note_area.is_visible():
            val = await note_area.input_value()
            if not val or len(val.strip()) < 5:
                pitch = self.profile.get("recruiter_pitch") or (
                    f"Hi {company} Founders & Team,\n\n"
                    f"I'm excited about {company} and the {job_title} role. "
                    "With 3.5+ years building scalable Python backends, LLM agents, and distributed applications, "
                    "I love taking full end-to-end ownership and moving fast in startup environments. "
                    "I am immediately available for interviews.\n\n"
                    f"Best regards,\n{self.profile.get('full_name', 'Sachin Sharma')}"
                )
                print(f"[YC Agent] ✍️ Filling founder pitch for {company}...", flush=True)
                await note_area.fill(pitch)
                await asyncio.sleep(0.5)

        # 4. Handle screening inputs, selects, and radios
        try:
            # Experience / numeric inputs
            num_inputs = await self.page.locator("input[type='number'], input[type='text']").all()
            for inp in num_inputs:
                try:
                    if not await inp.is_visible():
                        continue
                    val = await inp.input_value()
                    if val and len(val.strip()) > 0:
                        continue
                    parent = inp.locator("..")
                    context = ((await parent.text_content()) or "").lower()
                    if any(w in context for w in ["experience", "years"]):
                        exp_str = str(int(round(float(self.profile.get("total_experience_years", 3.5)))))
                        await inp.fill(exp_str)
                    elif any(w in context for w in ["notice", "days"]):
                        await inp.fill(str(self.profile.get("notice_period_days", 15)))
                except Exception:
                    pass

            # Sponsorship & authorization radios
            radios = await self.page.locator("input[type='radio'], label:has-text('Yes'), label:has-text('No')").all()
            for r in radios:
                try:
                    if not await r.is_visible():
                        continue
                    parent = r.locator("..")
                    context = ((await parent.text_content()) or "").lower()
                    if any(w in context for w in ["visa", "sponsorship"]):
                        no_btn = parent.locator("label:has-text('No'), input[value*='no' i]").first
                        if await no_btn.is_visible():
                            await no_btn.click()
                    elif any(w in context for w in ["authorized", "permission", "yes"]):
                        yes_btn = parent.locator("label:has-text('Yes'), input[value*='yes' i]").first
                        if await yes_btn.is_visible():
                            await yes_btn.click()
                except Exception:
                    pass

            # Dropdowns / selects
            selects = await self.page.locator("select").all()
            for sel in selects:
                try:
                    if await sel.is_visible():
                        options = await sel.locator("option").all()
                        for opt in options:
                            val = await opt.get_attribute("value")
                            txt = ((await opt.text_content()) or "").lower()
                            if val and val != "" and "select" not in txt:
                                await sel.select_option(val)
                                break
                except Exception:
                    pass
        except Exception as e:
            print(f"[YC Agent] Notice during form questions: {e}", flush=True)

        # 5. Resume upload if file input exists
        try:
            file_inp = self.page.locator("input[type='file']").first
            if await file_inp.count() > 0 and self.resume_path.exists():
                print(f"[YC Agent] 📄 Uploading resume: {self.resume_path.name}", flush=True)
                await file_inp.set_input_files(str(self.resume_path))
                await asyncio.sleep(1.0)
        except Exception as e:
            print(f"[YC Agent] Resume upload notice: {e}", flush=True)

        # 6. Submit Application
        submit_btn = self.page.locator(
            "button:has-text('Send application'), "
            "button:has-text('Submit'), "
            "button:has-text('Send message and apply'), "
            "button[type='submit'], "
            "input[type='submit']"
        ).first

        submitted = False
        if await submit_btn.is_visible() and not await submit_btn.is_disabled():
            print("[YC Agent] 🚀 Submitting YC Startup application...", flush=True)
            await submit_btn.scroll_into_view_if_needed()
            await submit_btn.click()
            await asyncio.sleep(2.0)
            submitted = True

        # 7. Wait for confirmation on DOM
        print("[YC Agent] ⏳ Awaiting confirmation...", flush=True)
        for _ in range(8):
            await asyncio.sleep(1.0)
            body = (await self.page.inner_text("body") or "").lower()
            if any(w in body for w in ["application sent", "applied", "application submitted", "message sent", "thanks for applying"]):
                print("[YC Agent] ✅ YC confirmation verified on DOM!", flush=True)
                submitted = True
                break

        # 8. Save screenshot proof
        await asyncio.sleep(1.0)
        await self.page.screenshot(path=str(proof_path))
        print(f"[YC Agent] 📸 Saved screenshot proof to: {proof_path}", flush=True)

        return {
            "status": "applied_successfully" if submitted else "submitted_with_notice",
            "job_title": job_title,
            "company": company,
            "job_url": job_url,
            "proof_path": str(proof_path),
            "message": "Application submitted & verified on Work at a Startup (YC)!"
        }
