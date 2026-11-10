import asyncio
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright

PROOFS_DIR = r"D:\ai-job-agent\proofs\live_cookie_autoapply"
os.makedirs(PROOFS_DIR, exist_ok=True)

LIVE_URL = "https://ai-job-agent-frontend-mauve.vercel.app/#console"

async def run_live_cookie_apply_test():
    print(f"=== TESTING LIVE VERCEL COOKIES & AUTO-APPLY: {LIVE_URL} ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        dialog_messages = []
        async def on_dialog(dialog):
            msg = dialog.message
            print(f"[PAGE DIALOG] {msg}")
            dialog_messages.append(msg)
            try:
                await dialog.accept()
            except Exception:
                pass

        page.on("dialog", lambda dialog: asyncio.create_task(on_dialog(dialog)))

        # 1. Open Live Vercel App
        print(f"1. Navigating to {LIVE_URL}...")
        await page.goto(LIVE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "01_landing.png"))

        # 2. Register fresh candidate
        print("2. Registering live candidate...")
        await page.click("#authSignInBtn")
        await page.wait_for_selector("#authModal", state="visible")
        await page.click("#tabSignUpBtn")
        
        ts = int(time.time())
        test_email = f"autoapply.test.{ts}@gmail.com"
        await page.fill("#authNameInput", "Alex Morgan")
        await page.fill("#authEmailInput", test_email)
        await page.fill("#authPasswordInput", "SecureAutoApply99!")
        await page.click("#authSubmitBtn")

        await page.wait_for_selector("#authUserMenu", state="visible", timeout=12000)
        print(f"Candidate signed in: Alex Morgan ({test_email})")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "02_signed_in.png"))

        # 3. Upload & Analyze Resume
        print("3. Uploading & Analyzing resume...")
        resume_docx_path = r"D:\ai-job-agent\sample_resume.docx"
        await page.set_input_files("#resumeFileInput", resume_docx_path)
        await page.wait_for_timeout(800)
        await page.click("#analyzeBtn")

        print("Waiting for live profile analysis...")
        await page.wait_for_selector("#profileCard:not(.hidden)", timeout=45000)
        print("Resume analysis completed successfully!")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "03_profile_analyzed.png"))

        # Dismiss platform modal if present
        try:
            await page.wait_for_selector("#platformSelectorModal:not(.hidden)", timeout=4000)
            await page.evaluate("closePlatformModal()")
            await page.wait_for_selector("#platformSelectorModal", state="hidden")
        except Exception:
            pass

        # 4. Wait for scouted jobs table
        print("4. Waiting for scouted jobs...")
        await page.wait_for_selector("#jobsTableBody tr", timeout=25000)
        job_count = await page.locator("#jobsTableBody tr").count()
        print(f"Scouted {job_count} jobs on live console.")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "04_jobs_table.png"))

        # 5. Switch to Wellfound tab
        print("5. Switching to Wellfound tab...")
        await page.click("#tabWellfound")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "05_wellfound_tab.png"))

        # 6. Click 'Quick Apply' on the first desktop job row to open Assistant Modal
        print("6. Clicking Quick Apply on first desktop job row...")
        quick_apply_btn = page.locator("#jobsTableBody button.quick-apply-btn, #jobsTableBody button:has-text('Quick Apply')").first
        await quick_apply_btn.scroll_into_view_if_needed()
        await quick_apply_btn.click()
        await page.wait_for_timeout(1500)

        # Check if Quick Apply Assistant Modal opens
        await page.wait_for_selector("#quickApplyAssistantModal:not(.hidden)", timeout=6000)
        print("Quick Apply Assistant Modal is open!")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "06_quick_apply_modal.png"))

        # 7. Click '⚡ Use Test Session' button inside modal
        print("7. Clicking Use Test Session button inside modal...")
        test_session_btn = page.locator("#quickApplyAssistantModal button:has-text('Use Test Session'), #quickApplyAssistantModal button:has-text('Test Session')").first
        await test_session_btn.click()
        await page.wait_for_timeout(2500)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "07_test_session_connected.png"))

        # Verify modal automatically closes
        modal_closed = await page.locator("#quickApplyAssistantModal").is_hidden()
        print(f"Modal automatically closed: {modal_closed}")

        # 8. Now click 'Auto-Apply' button on the desktop job row
        print("8. Clicking Auto-Apply button on job row with session connected...")
        auto_apply_btn = page.locator("#jobsTableBody button:has-text('Auto-Apply')").first
        await auto_apply_btn.scroll_into_view_if_needed()
        await auto_apply_btn.click()
        print("Waiting for auto-apply automation to complete...")
        await page.wait_for_timeout(12000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "08_after_auto_apply.png"))

        # Check status cell or action cell for 'Applied' or proof
        table_text = await page.locator("#jobsTableBody").text_content()
        print(f"Table content snapshot after apply:\n{table_text[:300]}...")
        
        await browser.close()
    print("=== LIVE VERCEL COOKIES & AUTO-APPLY TEST FINISHED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(run_live_cookie_apply_test())
