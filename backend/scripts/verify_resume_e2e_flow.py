import asyncio
import os
import sys
from playwright.async_api import async_playwright

PROOFS_DIR = r"D:\ai-job-agent\proofs\resume_analysis_e2e"
os.makedirs(PROOFS_DIR, exist_ok=True)

async def run_e2e():
    print("=== STARTING FULL END-TO-END RESUME ANALYSIS TEST ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        dialog_messages = []
        page.on("dialog", lambda dialog: (dialog_messages.append(dialog.message), dialog.accept()))

        # 1. Open Console
        print("1. Navigating to Console...")
        await page.goto("http://127.0.0.1:8000/#console", wait_until="networkidle")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "01_initial_landing.png"))

        # 2. Register candidate
        print("2. Registering test candidate...")
        await page.click("#authSignInBtn")
        await page.wait_for_selector("#authModal", state="visible")
        await page.click("#tabSignUpBtn")
        await page.fill("#authNameInput", "Sachin Sharma")
        await page.fill("#authEmailInput", "sachin.sharma.engineer@gmail.com")
        await page.fill("#authPasswordInput", "SecureTestPass123!")
        await page.click("#authSubmitBtn")

        # Wait for sign in to complete
        await page.wait_for_selector("#authUserMenu", state="visible", timeout=10000)
        user_name = await page.text_content("#userNameDisplay")
        print(f"Candidate signed in successfully: {user_name}")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "02_candidate_registered.png"))

        # 3. Upload Resume (.docx)
        print("3. Uploading dummy resume (sample_resume.docx)...")
        resume_docx_path = r"D:\ai-job-agent\sample_resume.docx"
        await page.set_input_files("#resumeFileInput", resume_docx_path)
        await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "03_resume_selected.png"))

        # 4. Click Analyze Resume with LLM
        print("4. Clicking 'Analyze Resume with LLM'...")
        await page.click("#analyzeBtn")

        # Wait for analysis to complete (profile card unhides or statParsed becomes 'Ready')
        print("Waiting for analysis results to render...")
        await page.wait_for_selector("#profileCard:not(.hidden)", timeout=40000)
        
        # Verify no error alerts were popped up
        error_alerts = [m for m in dialog_messages if "error" in m.lower() or "not defined" in m.lower()]
        if error_alerts:
            print(f"FAILED: Unexpected error dialog encountered: {error_alerts}")
            sys.exit(1)
        print("No error dialogs encountered!")

        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "04_resume_analyzed_profile_rendered.png"))

        # 5. Assert Profile Content
        cand_name_text = await page.text_content("#agentTargetCandidateName")
        parsed_status = await page.text_content("#statParsed")
        skills_count = await page.locator("#skillsContainer span, #skillsContainer button").count()
        print(f"Extracted Candidate Target: {cand_name_text}")
        print(f"Stat Parsed: {parsed_status}")
        print(f"Extracted Profile Skills Count: {skills_count}")

        assert "Sachin" in cand_name_text or len(cand_name_text) > 2, f"Candidate name not populated: {cand_name_text}"
        assert "Ready" in parsed_status or "Parsed" in parsed_status, f"Unexpected parsed status: {parsed_status}"
        assert skills_count > 0, "No skills badges rendered in skillsContainer"

        # 6. Platform Selector Modal Check & Dismiss
        print("6. Verifying Platform Selector Modal...")
        await page.wait_for_selector("#platformSelectorModal:not(.hidden)", timeout=5000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "05_platform_selector_modal.png"))
        await page.evaluate("closePlatformModal()")
        await page.wait_for_selector("#platformSelectorModal", state="hidden")

        # 7. Assert Job Scout Results
        print("7. Verifying Scouted Job Openings...")
        await page.wait_for_selector("#jobsTableBody tr", timeout=20000)
        job_rows = await page.locator("#jobsTableBody tr").count()
        print(f"Scouted job openings rendered: {job_rows} rows")
        assert job_rows > 0, "No jobs scouted"
        await page.screenshot(path=os.path.join(PROOFS_DIR, "06_scouted_jobs_rendered.png"))

        # 8. Test Memory Vault
        print("8. Testing Memory Vault...")
        await page.click("#navVaultBtn")
        await page.wait_for_selector("#memoryVaultModal", state="visible", timeout=5000)
        await page.wait_for_timeout(1000)
        vault_badge = await page.text_content("#vaultCountBadge")
        print(f"Memory Vault badge count: {vault_badge}")
        await page.screenshot(path=os.path.join(PROOFS_DIR, "07_memory_vault_modal.png"))
        await page.evaluate("toggleVaultModal(false)")
        await page.wait_for_selector("#memoryVaultModal", state="hidden")

        # 9. Test Platform Switcher
        print("9. Switching tabs between Naukri and Wellfound...")
        await page.click("#tabWellfound")
        await page.wait_for_timeout(500)
        apply_btn_text = await page.text_content("#runPlatformBtnText")
        assert "Wellfound" in apply_btn_text, f"Button text didn't update to Wellfound: {apply_btn_text}"
        await page.screenshot(path=os.path.join(PROOFS_DIR, "08_switched_to_wellfound.png"))

        await page.click("#tabNaukri")
        await page.wait_for_timeout(500)
        apply_btn_text = await page.text_content("#runPlatformBtnText")
        assert "Naukri" in apply_btn_text, f"Button text didn't update to Naukri: {apply_btn_text}"
        await page.screenshot(path=os.path.join(PROOFS_DIR, "09_switched_to_naukri.png"))

        # 10. Sign Out & Verify Empty State
        print("10. Signing out candidate...")
        await page.evaluate("handleSignOut()")
        await page.wait_for_selector("#authSignInBtn", state="visible", timeout=5000)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(PROOFS_DIR, "10_signed_out_empty_state.png"))

        await browser.close()
    print("=== FULL END-TO-END RESUME ANALYSIS & WORKFLOW TEST COMPLETED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(run_e2e())
