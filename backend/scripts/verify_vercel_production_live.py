import asyncio
import os
import sys
from playwright.async_api import async_playwright

PROOFS_DIR = r"D:\ai-job-agent\proofs\vercel_production_e2e"
os.makedirs(PROOFS_DIR, exist_ok=True)

LIVE_URL = "https://ai-job-agent-frontend-mauve.vercel.app/#console"

async def run_live_e2e():
    print(f"=== STARTING FULL LIVE VERCEL PRODUCTION E2E TEST: {LIVE_URL} ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        dialog_messages = []
        page.on("dialog", lambda dialog: (
            print(f"[PAGE DIALOG] {dialog.message}"),
            dialog_messages.append(dialog.message),
            dialog.accept()
        ))

        # 1. Open Live Vercel App
        print(f"1. Navigating to {LIVE_URL}...")
        await page.goto(LIVE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "01_live_vercel_landing.png"))

        # 2. Register / Sign in live candidate
        print("2. Registering / Signing in live test candidate...")
        await page.click("#authSignInBtn")
        await page.wait_for_selector("#authModal", state="visible")
        await page.click("#tabSignUpBtn")
        
        # Unique timestamped email to guarantee fresh tenant isolation
        import time
        ts = int(time.time())
        test_email = f"sachin.prod.{ts}@gmail.com"
        
        await page.fill("#authNameInput", "Sachin Sharma")
        await page.fill("#authEmailInput", test_email)
        await page.fill("#authPasswordInput", "SecureProdPass99!")
        await page.click("#authSubmitBtn")

        # Wait for sign in to complete
        await page.wait_for_selector("#authUserMenu", state="visible", timeout=12000)
        user_name = await page.text_content("#userNameDisplay")
        print(f"Candidate signed in successfully on live Vercel: {user_name} ({test_email})")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "02_live_candidate_registered.png"))

        # 3. Upload Dummy Resume (.docx)
        print("3. Uploading dummy resume to live Vercel app (sample_resume.docx)...")
        resume_docx_path = r"D:\ai-job-agent\sample_resume.docx"
        await page.set_input_files("#resumeFileInput", resume_docx_path)
        await page.wait_for_timeout(800)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "03_live_resume_selected.png"))

        # 4. Click Analyze Resume with LLM
        print("4. Clicking 'Analyze Resume with LLM' on live Vercel...")
        await page.click("#analyzeBtn")

        # Wait for analysis to complete and profile card to render
        print("Waiting for live resume analysis from Render backend...")
        await page.wait_for_selector("#profileCard:not(.hidden)", timeout=45000)
        
        # Verify no error alerts were triggered (specifically checking for 're' is not defined)
        error_alerts = [m for m in dialog_messages if "error" in m.lower() or "not defined" in m.lower() or "notice" in m.lower()]
        if error_alerts:
            print(f"FAILED: Unexpected error dialog encountered on live production: {error_alerts}")
            sys.exit(1)
        print("No error dialogs encountered! Live resume analysis completed with 0 errors!")

        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "04_live_resume_analyzed_profile_rendered.png"))

        # 5. Assert Profile Content
        cand_name_text = await page.text_content("#agentTargetCandidateName")
        parsed_status = await page.text_content("#statParsed")
        skills_count = await page.locator("#skillsContainer span, #skillsContainer button").count()
        print(f"Live Extracted Candidate Target: {cand_name_text}")
        print(f"Live Stat Parsed: {parsed_status}")
        print(f"Live Profile Skills Count: {skills_count}")

        assert "Sachin" in cand_name_text or len(cand_name_text) > 2, f"Candidate name not populated: {cand_name_text}"
        assert "Ready" in parsed_status or "Parsed" in parsed_status, f"Unexpected parsed status: {parsed_status}"
        assert skills_count > 0, "No skills badges rendered in skillsContainer"

        # 6. Verify Platform Selector Modal & Dismiss
        print("6. Verifying Platform Selector Modal on live Vercel...")
        await page.wait_for_selector("#platformSelectorModal:not(.hidden)", timeout=6000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "05_live_platform_selector_modal.png"))
        await page.evaluate("closePlatformModal()")
        await page.wait_for_selector("#platformSelectorModal", state="hidden")

        # 7. Assert Job Scout Results
        print("7. Verifying Scouted Job Openings on live Vercel...")
        await page.wait_for_selector("#jobsTableBody tr", timeout=25000)
        job_rows = await page.locator("#jobsTableBody tr").count()
        print(f"Live scouted job openings rendered: {job_rows} rows")
        assert job_rows > 0, "No jobs scouted"
        await page.screenshot(path=os.path.join(PROOFS_DIR, "06_live_scouted_jobs_rendered.png"))

        # 8. Test Memory Vault
        print("8. Testing Memory Vault on live Vercel...")
        await page.click("#navVaultBtn")
        await page.wait_for_selector("#memoryVaultModal", state="visible", timeout=6000)
        await page.wait_for_timeout(1000)
        vault_badge = await page.text_content("#vaultCountBadge")
        print(f"Live Memory Vault badge count: {vault_badge}")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "07_live_memory_vault_modal.png"))
        await page.evaluate("toggleVaultModal(false)")
        await page.wait_for_selector("#memoryVaultModal", state="hidden")

        # 9. Test Platform Switcher
        print("9. Switching tabs between Naukri and Wellfound on live Vercel...")
        await page.click("#tabWellfound")
        await page.wait_for_timeout(500)
        apply_btn_text = await page.text_content("#runPlatformBtnText")
        assert "Wellfound" in apply_btn_text, f"Button text didn't update to Wellfound: {apply_btn_text}"
        await page.screenshot(path=os.path.join(PROOFS_DIR, "08_live_switched_to_wellfound.png"))

        await page.click("#tabNaukri")
        await page.wait_for_timeout(500)
        apply_btn_text = await page.text_content("#runPlatformBtnText")
        assert "Naukri" in apply_btn_text, f"Button text didn't update to Naukri: {apply_btn_text}"
        await page.screenshot(path=os.path.join(PROOFS_DIR, "09_live_switched_to_naukri.png"))

        # 10. Sign Out & Verify Empty State
        print("10. Signing out live candidate...")
        await page.evaluate("handleSignOut()")
        await page.wait_for_selector("#authSignInBtn", state="visible", timeout=6000)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "10_live_signed_out_empty_state.png"))

        await browser.close()
    print("=== LIVE VERCEL PRODUCTION E2E RESUME & WORKFLOW TEST COMPLETED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(run_live_e2e())
