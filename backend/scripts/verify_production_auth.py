import os
import sys
import time
from playwright.sync_api import sync_playwright

PROOF_DIR = r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37\proofs_production_auth"
os.makedirs(PROOF_DIR, exist_ok=True)
PROD_URL = "https://ai-job-agent-frontend-mauve.vercel.app"

def sign_out(page):
    page.click("#authUserMenu button")
    page.wait_for_selector("#userDropdownPanel", state="visible")
    page.click("button:has-text('Sign Out')")
    page.wait_for_selector("#authSignInBtn", state="visible")

def run():
    print(f"[TEST] Verifying production deployment at {PROD_URL}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # 1. Open production page
        page.goto(PROD_URL, wait_until="networkidle")
        page.wait_for_selector("#authSignInBtn", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "01_prod_landing.png"))
        print("[PASS] 1. Production landing loaded cleanly.")

        # 2. Open Auth Modal
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        det_sec = page.query_selector("#detectedAccountsSection")
        assert "hidden" in det_sec.get_attribute("class"), "Detected accounts leaked in production!"
        print("[PASS] 2. Production auth modal opened; zero data leak.")

        # 3. Google 1-Click Fast Track
        page.click("#googleFallbackBtn")
        page.wait_for_selector("#googleAuthView", state="visible")
        page.click("button:has-text('1-Click Sign In')")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Sachin" in user_name, f"Expected Sachin in user name, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "02_prod_google_1click.png"))
        print(f"[PASS] 3. Production Google 1-Click sign-in verified: {user_name}")

        # 4. Sign Out
        sign_out(page)
        print("[PASS] 4. Production signed out cleanly.")

        # 5. GitHub 1-Click Fast Track
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.click("button:has-text('Continue with GitHub')")
        page.wait_for_selector("#githubAuthView", state="visible")
        page.click("#githubAuthView button:has-text('1-Click Sign In')")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Sachin-dev001" in user_name or "sachin" in user_name.lower(), f"Expected Sachin-dev001, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "03_prod_github_1click.png"))
        print(f"[PASS] 5. Production GitHub 1-Click sign-in verified: {user_name}")

        # 6. Sign Out
        sign_out(page)

        # 7. Production Email Seamless Auto-Registration
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.fill("#authEmailInput", "sachin.testprod@gmail.com")
        page.fill("#authPasswordInput", "ProductionPass123!")
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        page.screenshot(path=os.path.join(PROOF_DIR, "04_prod_email_signed_in.png"))
        print(f"[PASS] 6. Production email registration & sign-in verified: {user_name}")

        browser.close()
        print("\n[SUCCESS] PRODUCTION DEPLOYMENT FULLY VERIFIED AND PASSING 100%!")

if __name__ == "__main__":
    run()
