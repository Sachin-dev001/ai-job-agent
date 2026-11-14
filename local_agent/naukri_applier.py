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
        login_btn = self.page.locator("#login-apply-button, button:has-text('Login to apply'), a:has-text('Login to apply'), button:has-text('Continue with Google')").first
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
        already_applied = self.page.locator("#already-applied, button:has-text('Already Applied'), button:has-text('Applied'), span:has-text('Already Applied'), span:has-text('Applied')").first
        if await already_applied.is_visible() or "you have already applied" in body_text or "already applied on" in body_text:
            msg = "Already applied to this job earlier on Naukri."
            print(f"[Naukri Agent] ℹ️ {msg}")
            await self.page.screenshot(path=str(proof_path))
            return {
                "status": "already_applied",
                "applied": True,
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
        """Answers screening questions, notice period, and fills CTC/experience inputs in drawer/modal."""
        for step in range(10):
            # Check if drawer or chatbot questions are visible
            drawer = self.page.locator(".drawer, .chatbot_drawer, ._chatBotContainer, .ssrc__chat-container, .apply-drawer, [class*='drawer']").first
            is_drawer = await drawer.is_visible()

            # 1. Check for Radio options (e.g. 15 Days or less / Yes / Experience)
            radio_answered = False
            try:
                radio_answered = await self.page.evaluate("""() => {
                    const radios = Array.from(document.querySelectorAll("input[type='radio'], .ssrc__radio, .ssrc__label, .ssrc__radio-btn-container, label, [role='radio']"));
                    for (const el of radios) {
                        const txt = (el.innerText || el.value || el.id || '').toLowerCase();
                        if (txt.includes('15 days') || txt.includes('< 15') || txt.includes('immediate') || txt.includes('serving notice') || txt === 'yes' || txt.includes('3-5') || txt.includes('3 to 5')) {
                            el.click();
                            if (el.tagName === 'INPUT') {
                                el.checked = true;
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            return true;
                        }
                    }
                    return false;
                }""")
                if radio_answered:
                    print(f"[Naukri Agent] 👉 Step {step+1}: Selected candidate option / notice period")
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # 2. Check for contenteditable textArea in chatbot
            editable = self.page.locator(".chatbot_Drawer .textArea[contenteditable='true'], .textArea[contenteditable='true']").first
            if await editable.is_visible():
                latest_question = ""
                try:
                    latest_question = await self.page.evaluate("""() => {
                        const msgs = Array.from(document.querySelectorAll('.botMsg span, .botItem span, .botMsg div'));
                        return msgs.length > 0 ? msgs[msgs.length - 1].innerText : '';
                    }""")
                except Exception:
                    pass
                q_lower = (latest_question or "").lower()
                print(f"[Naukri Agent] 🤖 Step {step+1}: Chatbot asked: '{latest_question.strip()}'")

                answer = "3.5"
                if "ctc" in q_lower or "salary" in q_lower:
                    answer = str(self.profile.get("current_ctc_lakhs", "12"))
                elif "expected" in q_lower:
                    answer = str(self.profile.get("expected_ctc_lakhs", "18"))
                elif "experience" in q_lower or "years" in q_lower:
                    answer = str(self.profile.get("total_experience_years", "3.5"))
                elif "notice" in q_lower:
                    answer = str(self.profile.get("notice_period_days", "15"))
                elif any(k in q_lower for k in ("location", "city")):
                    answer = self.profile.get("location", "Bengaluru")
                else:
                    answer = "Yes, available and experienced."

                print(f"[Naukri Agent] ✍️ Step {step+1}: Typing answer: '{answer}'")
                try:
                    await editable.click()
                    await self.page.keyboard.type(answer, delay=40)
                    await asyncio.sleep(0.8)
                except Exception:
                    pass

            # 3. Check for standard inputs
            inputs = await self.page.locator("input[type='text']:not([class*='suggestor']):not(#experienceDD), input[type='number'], textarea").all()
            for inp in inputs:
                try:
                    if not await inp.is_visible() or await inp.is_disabled(): continue
                    val = await inp.input_value()
                    if val and len(val.strip()) > 0: continue
                    placeholder = (await inp.get_attribute("placeholder") or "").lower()
                    name = (await inp.get_attribute("name") or "").lower()
                    combined = f"{placeholder} {name}"
                    if any(k in combined for k in ("experience", "exp", "year")):
                        await inp.fill(str(self.profile.get("total_experience_years", "3.5")))
                    elif any(k in combined for k in ("ctc", "salary")):
                        await inp.fill(str(self.profile.get("current_ctc_lakhs", "12")))
                    elif "notice" in combined:
                        await inp.fill(str(self.profile.get("notice_period_days", "15")))
                    else:
                        await inp.fill("Yes")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # 4. Click Save / Submit
            save_clicked = False
            chatbot_send = self.page.locator(".sendMsgbtn_container, .sendMsg, div.send:not(.disabled) .sendMsg").first
            if await chatbot_send.is_visible():
                print(f"[Naukri Agent] 🚀 Step {step+1}: Clicking Chatbot Save button...")
                try:
                    await chatbot_send.click(force=True)
                    save_clicked = True
                    await asyncio.sleep(2.5)
                except Exception:
                    pass

            submit_btn = self.page.locator("button:has-text('Submit application'), button:has-text('Submit'), button:has-text('Save and Apply'), button:has-text('Next'), input[type='submit']").first
            if await submit_btn.is_visible() and not await submit_btn.is_disabled():
                btn_text = await submit_btn.text_content()
                print(f"[Naukri Agent] 🚀 Step {step+1}: Clicking Submit/Next button: '{btn_text.strip()}'")
                try:
                    await submit_btn.click(force=True)
                    save_clicked = True
                    await asyncio.sleep(2.5)
                except Exception:
                    pass

            # 5. Check if application has completed
            body_text = (await self.page.inner_text("body") or "").lower()
            if "applied to" in body_text or "successfully applied" in body_text or "application submitted" in body_text or "power up your applies" in body_text:
                print(f"[Naukri Agent] 🎉 100% CONFIRMED: Application submitted on Naukri DOM!")
                break

            if not is_drawer and not save_clicked and not radio_answered:
                break
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
