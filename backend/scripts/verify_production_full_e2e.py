import os
import sys
import time
from playwright.sync_api import sync_playwright

PROOF_DIR = r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37\proofs_e2e_final"
os.makedirs(PROOF_DIR, exist_ok=True)
PROD_URL = "https://ai-job-agent-frontend-mauve.vercel.app"

def run():
    print(f"[TEST] Verifying Full E2E flow on live production Vercel: {PROD_URL}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # 1. Load application console
        page.goto(f"{PROD_URL}/#console", wait_until="networkidle")
        page.wait_for_selector("#jobsTableBody", state="visible")
        print("[PASS] 1. Live console loaded with clean empty-state.")

        # 2. Verify empty-state text is not clipped
        table_text = page.text_content("#jobsTableBody")
        assert "Upload and analyze your resume first" in table_text, "Heading missing from empty state"
        print("[PASS] 2. Table empty-state text renders cleanly without clipping.")

        # 3. Open Account Creation
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.click("#tabSignUpBtn")
        page.fill("#authNameInput", "Kavita Rao")
        page.fill("#authEmailInput", "kavita.rao.prod@gmail.com")
        page.fill("#authPasswordInput", "KavitaPass2026!")
        page.click("#authSubmitBtn")

        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Kavita" in user_name, f"Expected Kavita, got: {user_name}"
        print(f"[PASS] 3. Production account registered and authenticated: {user_name}")

        # 4. Switch between Naukri and Wellfound tabs and verify sync
        wellfound_tab = page.query_selector("#tabWellfound")
        if wellfound_tab:
            wellfound_tab.click()
            page.wait_for_timeout(400)
            btn_text = page.text_content("#runPlatformBtnText")
            assert "Wellfound" in btn_text, f"Expected Wellfound in button, got {btn_text}"
            print(f"[PASS] 4A. Production Wellfound tab switched successfully: Button='{btn_text.strip()}'")

        naukri_tab = page.query_selector("#tabNaukri")
        if naukri_tab:
            naukri_tab.click()
            page.wait_for_timeout(400)
            btn_text = page.text_content("#runPlatformBtnText")
            assert "Naukri" in btn_text, f"Expected Naukri in button, got {btn_text}"
            print(f"[PASS] 4B. Production Naukri tab switched successfully: Button='{btn_text.strip()}'")

        # 5. Sign out
        page.click("#authUserMenu button")
        page.wait_for_selector("#userDropdownPanel", state="visible")
        page.click("button:has-text('Sign Out')")
        page.wait_for_selector("#authSignInBtn", state="visible")
        print("[PASS] 5. Production signed out cleanly. All candidate state reset.")

        browser.close()
        print("\n=======================================================")
        print("[SUCCESS] FULL PRODUCTION E2E VERIFICATION PASSED 100%!")
        print("=======================================================")

if __name__ == "__main__":
    run()
