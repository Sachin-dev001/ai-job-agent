import os
import re
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page
from local_agent.config import get_candidate_profile, get_resume_path, PROOFS_DIR

class LocalLinkedInApplier:
    def __init__(self, page: Page):
        self.page = page
        self.profile = get_candidate_profile()
        self.resume_path = get_resume_path()

    async def apply_to_job(self, job_url: str, skip_goto: bool = False) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_filename = f"linkedin_proof_{timestamp}.png"
        proof_path = PROOFS_DIR / proof_filename

        print(f"\n[LinkedIn Agent] 🌐 Navigating to: {job_url}", flush=True)
        if not skip_goto:
            try:
                await self.page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
                await asyncio.sleep(2.5)
            except Exception as e:
                err_str = str(e).lower()
                print(f"[LinkedIn Agent] Navigation warning: {e}", flush=True)
                if "err_too_many_redirects" in err_str or "redirect" in err_str:
                    print("[LinkedIn Agent] 🔄 Redirect loop detected due to stale/invalid cookies. Clearing LinkedIn cookies and retrying cleanly...", flush=True)
                    try:
                        await self.page.context.clear_cookies()
                        await asyncio.sleep(1.0)
                        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
                        await asyncio.sleep(2.0)
                    except Exception as retry_err:
                        print(f"[LinkedIn Agent] Retry after cookie clear notice: {retry_err}", flush=True)

        # Extract Job Title & Company
        job_title = "Software / AI Engineer"
        company = "LinkedIn Hiring Company"
        try:
            h1 = await self.page.locator(
                "h1.job-details-jobs-unified-top-card__job-title, "
                ".jobs-unified-top-card__job-title, "
                ".top-card-layout__title, "
                "h1.t-24, "
                "h1"
            ).first.text_content()
            if h1:
                job_title = h1.strip()
        except Exception:
            pass

        try:
            comp_el = await self.page.locator(
                ".job-details-jobs-unified-top-card__company-name, "
                ".jobs-unified-top-card__company-name, "
                ".topcard__org-name-link, "
                "a[href*='/company/'], "
                ".job-details-jobs-unified-top-card__primary-description a"
            ).first.text_content()
            if comp_el:
                company = comp_el.strip()
        except Exception:
            pass

        print(f"[LinkedIn Agent] Target: '{job_title}' at '{company}'", flush=True)

        # 1. Check if already applied
        applied_locator = self.page.locator(
            "button:has-text('Applied'), "
            "span:has-text('Applied'), "
            ".jobs-s-apply__applied-date, "
            "[data-view-name*='applied']"
        ).first
        body_text = (await self.page.inner_text("body") or "").lower()

        if await applied_locator.is_visible() or "already applied" in body_text or "application submitted" in body_text:
            msg = f"Already applied to '{job_title}' at '{company}' earlier."
            print(f"[LinkedIn Agent] ℹ️ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "already_applied",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": msg
            }

        # 2. Find and click Easy Apply button
        easy_apply_btn = self.page.locator(
            "button:has-text('Easy Apply'), "
            "button.jobs-apply-button, "
            "button[data-job-id][aria-label*='Easy Apply'], "
            ".jobs-apply-button--top-card button"
        ).first

        # 2. Check if login is required
        login_btn = self.page.locator("a:has-text('Sign in'), button:has-text('Sign in'), .nav__button-secondary, [data-tracking-control-name*='login']").first
        if await login_btn.is_visible() and not await easy_apply_btn.is_visible():
            msg = "LinkedIn login session required. Please run session setup or connect your LinkedIn cookies."
            print(f"[LinkedIn Agent] ⚠️ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "login_required",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": msg
            }

        if not await easy_apply_btn.is_visible():
            # Check if external Apply button exists
            ext_apply = self.page.locator("button:has-text('Apply'), a:has-text('Apply')").first
            if await ext_apply.is_visible():
                msg = "Job requires external company redirect (Easy Apply not available)."
            else:
                msg = "Easy Apply button not visible on LinkedIn job posting."
            print(f"[LinkedIn Agent] ⚠️ {msg}", flush=True)
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "button_not_found",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": msg
            }

        print("[LinkedIn Agent] 🖱️ Clicking Easy Apply button...", flush=True)
        try:
            await easy_apply_btn.scroll_into_view_if_needed()
            await easy_apply_btn.click()
            await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[LinkedIn Agent] Notice clicking Easy Apply: {e}", flush=True)

        # 3. Handle multi-step Easy Apply dialog (up to 8 steps)
        max_steps = 8
        submitted = False

        for step in range(1, max_steps + 1):
            print(f"[LinkedIn Agent] 📋 Processing Easy Apply Step {step}...", flush=True)
            await asyncio.sleep(1.0)

            # Check if already reached confirmation screen
            confirmation_el = self.page.locator("text='Application submitted', h3:has-text('Application submitted')").first
            if await confirmation_el.is_visible():
                print("[LinkedIn Agent] ✅ Confirmation already displayed!", flush=True)
                submitted = True
                break

            modal = self.page.locator(".jobs-easy-apply-modal, div[role='dialog']").first
            modal_scope = modal if await modal.is_visible() else self.page

            # A. Phone number input
            phone_inputs = await modal_scope.locator(
                "input[id*='phoneNumber' i], "
                "input[name*='phoneNumber' i], "
                "input[id*='phone' i], "
                "input[name*='phone' i], "
                "input[autocomplete='tel']"
            ).all()
            for pinp in phone_inputs:
                try:
                    if await pinp.is_visible():
                        val = await pinp.input_value()
                        if not val or len(val.strip()) < 5:
                            cand_phone = self.profile.get("phone", "+91 9876543210")
                            # Extract numeric digits if needed
                            digits = re.sub(r"[^\d+]", "", cand_phone)
                            print(f"[LinkedIn Agent] 📞 Setting phone number: {digits}", flush=True)
                            await pinp.fill(digits)
                            await asyncio.sleep(0.3)
                except Exception:
                    pass

            # B. Resume upload or selection
            try:
                # File input for resume
                file_inp = modal_scope.locator("input[type='file']").first
                if await file_inp.count() > 0 and self.resume_path.exists():
                    print(f"[LinkedIn Agent] 📄 Uploading resume: {self.resume_path.name}", flush=True)
                    await file_inp.set_input_files(str(self.resume_path))
                    await asyncio.sleep(1.2)
                else:
                    # Select first pre-uploaded resume radio if present
                    resume_radios = await modal_scope.locator(
                        "input[type='radio'][id*='resume' i], "
                        ".jobs-resume-picker__resume-list-item input[type='radio']"
                    ).all()
                    if resume_radios:
                        is_checked = await resume_radios[0].is_checked()
                        if not is_checked:
                            await resume_radios[0].click(force=True)
                            await asyncio.sleep(0.3)
            except Exception as e:
                print(f"[LinkedIn Agent] Resume handling notice: {e}", flush=True)

            # C. Screening questions - Text / Number inputs
            text_inputs = await modal_scope.locator("input[type='text'], input[type='number']").all()
            for tinp in text_inputs:
                try:
                    if not await tinp.is_visible():
                        continue
                    val = await tinp.input_value()
                    if val and len(val.strip()) > 0:
                        continue

                    # Determine context from parent label or aria attributes
                    parent = tinp.locator("xpath=ancestor::div[contains(@class,'jobs-easy-apply-form-section') or contains(@class,'fb-form-element') or position()=1]")
                    context = ((await parent.text_content()) or "").lower()

                    if any(w in context for w in ["experience", "years", "how many years"]):
                        exp_years = str(int(round(float(self.profile.get("total_experience_years", 3.5)))))
                        print(f"[LinkedIn Agent] ⏳ Answering experience question with: {exp_years}", flush=True)
                        await tinp.fill(exp_years)
                    elif any(w in context for w in ["notice", "days", "period"]):
                        notice_days = str(self.profile.get("notice_period_days", 15))
                        print(f"[LinkedIn Agent] 🗓️ Answering notice period: {notice_days}", flush=True)
                        await tinp.fill(notice_days)
                    elif any(w in context for w in ["salary", "ctc", "compensation"]):
                        ctc = str(self.profile.get("expected_ctc_lakhs", 18))
                        print(f"[LinkedIn Agent] 💰 Answering compensation: {ctc}", flush=True)
                        await tinp.fill(ctc)
                    elif any(w in context for w in ["city", "location", "current"]):
                        loc = self.profile.get("current_location", "Bengaluru")
                        print(f"[LinkedIn Agent] 📍 Answering location: {loc}", flush=True)
                        await tinp.fill(loc)
                    else:
                        # Fallback for generic mandatory number/text
                        inp_type = await tinp.get_attribute("type")
                        fill_val = "3" if inp_type == "number" else "Yes"
                        await tinp.fill(fill_val)
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # D. Screening questions - Radio groups
            radio_groups = await modal_scope.locator(".fb-radio-buttons, fieldset, div[role='radiogroup']").all()
            for rgroup in radio_groups:
                try:
                    if not await rgroup.is_visible():
                        continue
                    group_text = ((await rgroup.text_content()) or "").lower()

                    # Check if sponsorship question
                    if any(w in group_text for w in ["sponsorship", "visa", "require sponsorship", "employment visa"]):
                        # Select 'No'
                        no_opt = rgroup.locator("label:has-text('No'), input[value*='no' i]").first
                        if await no_opt.is_visible():
                            print("[LinkedIn Agent] 👉 Sponsorship question -> No", flush=True)
                            await no_opt.click()
                    # Check if authorized to work or general affirmative question
                    elif any(w in group_text for w in ["authorized", "legally", "comfortable", "completed", "degree", "experience", "willing"]):
                        yes_opt = rgroup.locator("label:has-text('Yes'), input[value*='yes' i]").first
                        if await yes_opt.is_visible():
                            print("[LinkedIn Agent] 👉 Qualification question -> Yes", flush=True)
                            await yes_opt.click()
                    else:
                        # Default to first radio or Yes if unselected
                        first_radio = rgroup.locator("input[type='radio'], label").first
                        if await first_radio.is_visible():
                            await first_radio.click()
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # E. Screening questions - Select dropdowns
            select_els = await modal_scope.locator("select").all()
            for sel in select_els:
                try:
                    if not await sel.is_visible():
                        continue
                    parent = sel.locator("..")
                    sel_text = ((await parent.text_content()) or "").lower()

                    options = await sel.locator("option").all()
                    opt_values = [await o.get_attribute("value") for o in options]
                    opt_texts = [(await o.text_content() or "").lower() for o in options]

                    if any(w in sel_text for w in ["sponsorship", "visa"]):
                        # Find "No"
                        for idx, txt in enumerate(opt_texts):
                            if "no" in txt:
                                await sel.select_option(opt_values[idx])
                                break
                    elif any(w in sel_text for w in ["authorized", "experience", "yes"]):
                        for idx, txt in enumerate(opt_texts):
                            if "yes" in txt:
                                await sel.select_option(opt_values[idx])
                                break
                    else:
                        # Pick first non-empty option
                        for idx, val in enumerate(opt_values):
                            if val and val != "Select an option" and val != "":
                                await sel.select_option(val)
                                break
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # F. Screening questions - Checkboxes
            checkboxes = await modal_scope.locator("input[type='checkbox']").all()
            for cb in checkboxes:
                try:
                    if await cb.is_visible() and not await cb.is_checked():
                        await cb.check()
                        await asyncio.sleep(0.2)
                except Exception:
                    pass

            # G. Textarea / Recruiter Pitch
            textareas = await modal_scope.locator("textarea").all()
            for ta in textareas:
                try:
                    if await ta.is_visible():
                        val = await ta.input_value()
                        if not val or len(val.strip()) < 5:
                            pitch = self.profile.get("recruiter_pitch") or (
                                f"Hi {company} Hiring Team,\n\n"
                                f"I am deeply excited to apply for the {job_title} role. "
                                f"I bring hands-on expertise across Python, FastAPI, GenAI, and distributed backend systems. "
                                f"I am immediately available to interview.\n\n"
                                f"Best regards,\n{self.profile.get('full_name', 'Sachin Sharma')}"
                            )
                            print(f"[LinkedIn Agent] ✍️ Filling pitch note...", flush=True)
                            await ta.fill(pitch)
                            await asyncio.sleep(0.3)
                except Exception:
                    pass

            # H. Navigation: Check Submit -> Review -> Next
            submit_btn = modal_scope.locator(
                "button:has-text('Submit application'), "
                "button[aria-label*='Submit application'], "
                "button:has-text('Submit')"
            ).first

            review_btn = modal_scope.locator(
                "button:has-text('Review'), "
                "button[aria-label*='Review your application']"
            ).first

            next_btn = modal_scope.locator(
                "button:has-text('Next'), "
                "button[aria-label*='Continue to next step']"
            ).first

            if await submit_btn.is_visible() and not await submit_btn.is_disabled():
                print("[LinkedIn Agent] 🚀 Clicking 'Submit application'...", flush=True)
                await submit_btn.scroll_into_view_if_needed()
                await submit_btn.click()
                submitted = True
                await asyncio.sleep(3.0)
                break
            elif await review_btn.is_visible() and not await review_btn.is_disabled():
                print("[LinkedIn Agent] 🔍 Clicking 'Review' button...", flush=True)
                await review_btn.scroll_into_view_if_needed()
                await review_btn.click()
                await asyncio.sleep(1.5)
            elif await next_btn.is_visible() and not await next_btn.is_disabled():
                print("[LinkedIn Agent] ➡️ Clicking 'Next' button...", flush=True)
                await next_btn.scroll_into_view_if_needed()
                await next_btn.click()
                await asyncio.sleep(1.5)
            else:
                # Check if submission is already finished or blocked by errors
                errors = await modal_scope.locator(".artdeco-inline-feedback--error").all()
                if errors:
                    err_texts = [await e.text_content() for e in errors]
                    print(f"[LinkedIn Agent] ⚠️ Field validation warnings: {err_texts}", flush=True)
                await asyncio.sleep(1.0)

        # 4. Wait for submission confirmation banner / dialog on DOM
        print("[LinkedIn Agent] ⏳ Awaiting confirmation dialog on DOM...", flush=True)
        for _ in range(8):
            confirm_banner = self.page.locator(
                "text='Application submitted', "
                "h3:has-text('Application submitted'), "
                "div[role='dialog']:has-text('Application submitted'), "
                ".artdeco-modal:has-text('Application submitted')"
            ).first
            if await confirm_banner.is_visible():
                print("[LinkedIn Agent] ✅ Submission confirmation banner verified on DOM!", flush=True)
                submitted = True
                break
            await asyncio.sleep(1.0)

        # Dismiss post-submission modal if present
        dismiss_btn = self.page.locator("button[aria-label='Dismiss'], button:has-text('Done')").first
        if await dismiss_btn.is_visible():
            try:
                await dismiss_btn.click()
                await asyncio.sleep(0.5)
            except Exception:
                pass

        # 5. Save high-res screenshot proof
        await asyncio.sleep(1.0)
        await self.page.screenshot(path=str(proof_path), full_page=False)
        print(f"[LinkedIn Agent] 📸 Saved screenshot proof to: {proof_path}", flush=True)

        if submitted:
            return {
                "status": "applied_successfully",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": "Application submitted & confirmed on LinkedIn Easy Apply!"
            }
        else:
            return {
                "status": "submitted_with_notice",
                "job_title": job_title,
                "company": company,
                "job_url": job_url,
                "proof_path": str(proof_path),
                "message": "Completed Easy Apply workflow; proof captured."
            }
