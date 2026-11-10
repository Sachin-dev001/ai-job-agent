import asyncio
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from playwright.async_api import async_playwright

async def run_tests():
    url = "http://127.0.0.1:8000"
    proofs_dir = Path("D:/ai-job-agent/backend/proofs")
    proofs_dir.mkdir(parents=True, exist_ok=True)
    resume_path = "D:/ai-job-agent/backend/sample_resume.txt"

    print(f"Starting Playwright verification against {url}...", flush=True)

    console_errors = []
    failed_assertions = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        def on_console(msg):
            # Ignore harmless external network / favicon / Supabase / Google GSI demo logs
            if msg.type == "error":
                text = msg.text
                if not any(ign in text for ign in ["favicon.ico", "accounts.google.com", "supabase", "Failed to load resource", "GSI_LOGGER", "Provider's accounts list"]):
                    console_errors.append(text)

        page.on("console", on_console)

        print("\n--- [Step 1] Loading Fresh Frontend State ---", flush=True)
        await page.goto(url, wait_until="networkidle", timeout=20000)
        await page.wait_for_timeout(1000)

        # 1. Candidate Name in Console Header
        cand_name = await page.inner_text("#agentTargetCandidateName")
        print(f"1. Candidate Name: '{cand_name}' (expected: 'Candidate')", flush=True)
        if cand_name.strip() != "Candidate":
            failed_assertions.append(f"Expected Candidate Name 'Candidate', got '{cand_name}'")

        # 2. Stat Card: Parsed
        stat_parsed = await page.inner_text("#statParsed")
        stat_sub = await page.inner_text("#statParsedSubtitle")
        print(f"2. Stat Parsed: '{stat_parsed}', Subtitle: '{stat_sub}' (expected: 'Awaiting', 'Upload resume to start')", flush=True)
        if "awaiting" not in stat_parsed.lower():
            failed_assertions.append(f"Expected Stat Parsed 'Awaiting', got '{stat_parsed}'")

        # 3. Stat Card: Needs Human
        stat_human = await page.inner_text("#statNeedsHuman")
        print(f"3. Stat Needs Human: '{stat_human}' (expected: '0')", flush=True)
        if stat_human.strip() != "0":
            failed_assertions.append(f"Expected Stat Needs Human '0', got '{stat_human}'")

        # 4. Vault Ticker Fact Count
        vault_ticker = await page.inner_text("#vaultFactCountTop")
        print(f"4. Vault Ticker: '{vault_ticker}' (expected: '0 Facts')", flush=True)
        if "0 facts" not in vault_ticker.lower():
            failed_assertions.append(f"Expected Vault Ticker '0 Facts', got '{vault_ticker}'")

        # 5. Dropzone Placeholder Text
        drop_text = await page.inner_text("#resumePlaceholderText")
        print(f"5. Dropzone Text: '{drop_text}'", flush=True)
        if "sachin" in drop_text.lower():
            failed_assertions.append(f"Dropzone contains hardcoded 'Sachin': '{drop_text}'")

        # 6. Openings Heading & Table Empty State
        heading = await page.inner_text("#openingsHeading")
        print(f"6. Openings Heading: '{heading.strip()}' (expected: contains 'Awaiting Resume Analysis')", flush=True)
        if "awaiting resume analysis" not in heading.lower():
            failed_assertions.append(f"Expected Openings Heading to contain 'Awaiting Resume Analysis', got '{heading}'")

        table_body_text = await page.inner_text("#jobsTableBody")
        print(f"7. Jobs Table Empty State text preview: '{table_body_text[:80]}...'", flush=True)
        if "upload and analyze your resume first" not in table_body_text.lower():
            failed_assertions.append("Jobs table does not show resume requirement empty state")

        # Capture Clean State Proof
        await page.screenshot(path=str(proofs_dir / "proof_clean_state.png"))
        print("Captured screenshot: proof_clean_state.png", flush=True)

        print("\n--- [Step 2] Testing Platform Switching Guard (Without Resume) ---", flush=True)
        # Click Wellfound platform tab
        await page.click("#tabWellfound")
        await page.wait_for_timeout(500)
        heading_wf = await page.inner_text("#openingsHeading")
        table_body_wf = await page.inner_text("#jobsTableBody")
        print(f"Wellfound Heading: '{heading_wf.strip()}'", flush=True)
        if "awaiting resume analysis" not in heading_wf.lower():
            failed_assertions.append("Wellfound switch did not guard against job load before resume")
        if "upload and analyze your resume first" not in table_body_wf.lower():
            failed_assertions.append("Wellfound view lost empty state without resume")

        # Switch back to Naukri
        await page.click("#tabNaukri")
        await page.wait_for_timeout(500)

        print("\n--- [Step 3] Testing Auth Modal & GIS Integration ---", flush=True)
        # Open Auth Modal
        await page.click("#authSignInBtn")
        await page.wait_for_timeout(500)
        auth_modal_visible = await page.is_visible("#authModal:not(.hidden)")
        print(f"Auth Modal Visible: {auth_modal_visible}", flush=True)
        if not auth_modal_visible:
            failed_assertions.append("Auth Modal failed to open upon clicking Sign In")

        # Verify Google GIS SDK script in head
        gis_script = await page.query_selector('script[src*="accounts.google.com/gsi/client"]')
        print(f"Google GIS SDK Script present: {gis_script is not None}", flush=True)
        if not gis_script:
            failed_assertions.append("Google Identity Services (GSI) script tag missing from HTML")

        # Verify Google GIS button container
        gsi_modal_btn = await page.query_selector("#googleGsiBtnModal")
        print(f"Google GSI Button container #googleGsiBtnModal present: {gsi_modal_btn is not None}", flush=True)
        if not gsi_modal_btn:
            failed_assertions.append("Container #googleGsiBtnModal missing from auth modal")

        # Verify Real OAuth Buttons (Google & GitHub)
        google_btn = await page.query_selector("#authModal button:has-text('Continue with Google')")
        github_btn = await page.query_selector("#authModal button:has-text('Continue with GitHub')")
        print(f"Google button present: {google_btn is not None}", flush=True)
        print(f"GitHub button present: {github_btn is not None}", flush=True)
        if not google_btn or not github_btn:
            failed_assertions.append("Google or GitHub trigger buttons missing")

        # Verify Auto-Detected Gmail Accounts Section
        detected_sec = await page.is_visible("#detectedAccountsSection:not(.hidden)")
        print(f"Detected Accounts Section visible: {detected_sec}", flush=True)
        if not detected_sec:
            failed_assertions.append("Detected Accounts Section #detectedAccountsSection not visible")

        # Test 1-click auto-fill on first detected Gmail pill
        first_pill = await page.query_selector("#detectedAccountsPills > div")
        if first_pill:
            await first_pill.click()
            await page.wait_for_timeout(300)
            email_val = await page.input_value("#authEmailInput")
            print(f"1-Click Auto-Filled Email: '{email_val}'", flush=True)
            if not email_val or "gmail.com" not in email_val:
                failed_assertions.append(f"Expected 1-click auto-fill to populate a Gmail address, got '{email_val}'")
        else:
            failed_assertions.append("No detected account pills rendered in #detectedAccountsPills")

        # Verify NO fake forms for Google/GitHub typing
        fake_google_input = await page.query_selector("#authModal input[placeholder*='Google account email']")
        fake_github_input = await page.query_selector("#authModal input[placeholder*='GitHub username']")
        print(f"Fake Google input present: {fake_google_input is not None} (expected: False)", flush=True)
        print(f"Fake GitHub input present: {fake_github_input is not None} (expected: False)", flush=True)
        if fake_google_input or fake_github_input:
            failed_assertions.append("Fake mock forms for Google or GitHub are still present in auth modal")

        # Capture Auth Modal Proof
        await page.screenshot(path=str(proofs_dir / "proof_auth_modal.png"))
        print("Captured screenshot: proof_auth_modal.png", flush=True)

        # Close Auth Modal with ESC
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)

        print("\n--- [Step 4] Resume Upload & Dynamic Post-Analysis Transition ---", flush=True)
        if os.path.exists(resume_path):
            file_input = await page.query_selector("#resumeFileInput")
            await file_input.set_input_files(resume_path)
            await page.wait_for_timeout(500)

            # Trigger LLM Analysis
            print("Triggering LLM resume analysis...", flush=True)
            await page.click("#analyzeBtn")

            # Wait for analysis to complete and update candidate profile
            print("Waiting for candidate name and status to update...", flush=True)
            try:
                await page.wait_for_function(
                    "() => document.getElementById('agentTargetCandidateName')?.textContent?.trim() !== 'Candidate'",
                    timeout=30000
                )
            except Exception as e:
                print(f"Timeout waiting for candidate name update: {e}", flush=True)

            cand_name_post = await page.inner_text("#agentTargetCandidateName")
            stat_parsed_post = await page.inner_text("#statParsed")
            drop_text_post = await page.inner_text("#resumePlaceholderText")
            heading_post = await page.inner_text("#openingsHeading")

            print(f"Post-Analysis Candidate Name: '{cand_name_post}'", flush=True)
            print(f"Post-Analysis Stat Parsed: '{stat_parsed_post}'", flush=True)
            print(f"Post-Analysis Dropzone Text: '{drop_text_post}'", flush=True)
            print(f"Post-Analysis Openings Heading: '{heading_post.strip()}'", flush=True)

            if "john" not in cand_name_post.lower():
                failed_assertions.append(f"Expected candidate name to contain 'John', got '{cand_name_post}'")
            if "ready" not in stat_parsed_post.lower():
                failed_assertions.append(f"Expected stat parsed 'Ready', got '{stat_parsed_post}'")

            # Wait a few seconds for job search results
            await page.wait_for_timeout(3000)

            # Close Platform Modal if open
            if await page.is_visible("#platformSelectorModal:not(.hidden)"):
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(400)

            # Capture Post-Resume Proof
            await page.screenshot(path=str(proofs_dir / "proof_post_resume.png"))
            print("Captured screenshot: proof_post_resume.png", flush=True)

        else:
            failed_assertions.append(f"Sample resume file missing at {resume_path}")

        await browser.close()

    print("\n--- Summary ---", flush=True)
    if console_errors:
        print(f"Encountered {len(console_errors)} unexpected console errors:")
        for err in console_errors:
            print(f"  - {err}")
    else:
        print("Zero console errors!")

    if failed_assertions:
        print(f"FAILED ({len(failed_assertions)} errors):")
        for f in failed_assertions:
            print(f"  ❌ {f}")
        sys.exit(1)
    else:
        print("🎉 ALL PLAYWRIGHT CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
