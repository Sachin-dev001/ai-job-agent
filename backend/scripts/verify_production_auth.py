import os
import sys
import time
from playwright.sync_api import sync_playwright

PROOF_DIR = r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37\proofs_production_email_auth"
os.makedirs(PROOF_DIR, exist_ok=True)
PROD_URL = "https://ai-job-agent-frontend-mauve.vercel.app"

def sign_out(page):
    page.click("#authUserMenu button")
    page.wait_for_selector("#userDropdownPanel", state="visible")
    page.click("button:has-text('Sign Out')")
    page.wait_for_selector("#authSignInBtn", state="visible")

def run():
    print(f"[TEST] Verifying production strict email auth at {PROD_URL}...")
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
        
        # Verify zero Google or GitHub buttons
        assert page.query_selector("#googleFallbackBtn") is None, "Google button found in production!"
        assert page.query_selector("#googleAuthView") is None, "Google view found in production!"
        assert page.query_selector("#githubAuthView") is None, "GitHub view found in production!"
        assert page.query_selector("#detectedAccountsSection") is None, "Detected accounts found in production!"
        
        page.screenshot(path=os.path.join(PROOF_DIR, "02_prod_clean_auth_modal.png"))
        print("[PASS] 2. Production auth modal opened; 100% email-only with zero Google/GitHub leaks.")

        # 3. Try to sign in as new user without registering
        page.fill("#authEmailInput", "new.candidate.2026@gmail.com")
        page.fill("#authPasswordInput", "SecurePass123!")
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authErrorMsg", state="visible")
        err_msg = page.text_content("#authErrorText")
        assert "No account found" in err_msg, f"Expected 'No account found', got: {err_msg}"
        print(f"[PASS] 3. Unregistered user blocked from sign in: '{err_msg}'")

        # 4. Switch to Create Account tab and register
        page.click("#tabSignUpBtn")
        page.wait_for_selector("#signUpNameField", state="visible")
        page.fill("#authNameInput", "Ananya Sharma")
        page.fill("#authEmailInput", "ananya.sharma@gmail.com")
        page.fill("#authPasswordInput", "SecurePass123!")
        page.click("#authSubmitBtn")

        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Ananya" in user_name, f"Expected Ananya in user name, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "03_prod_user_registered.png"))
        print(f"[PASS] 4. User registered and signed into private session: {user_name}")

        # 5. Sign out
        sign_out(page)
        print("[PASS] 5. Signed out cleanly.")

        # 6. Re-open modal and verify fields are cleared
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        email_val = page.input_value("#authEmailInput")
        assert email_val == "", f"Email leaked on logout: {email_val}"
        
        # 7. Sign in with registered credentials
        page.fill("#authEmailInput", "ananya.sharma@gmail.com")
        page.fill("#authPasswordInput", "SecurePass123!")
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Ananya" in user_name, f"Expected Ananya, got {user_name}"
        print(f"[PASS] 6. Registered user logged back in successfully: {user_name}")

        browser.close()
        print("\n[SUCCESS] ALL PRODUCTION STRICT EMAIL/PASSWORD TESTS PASSED!")

if __name__ == "__main__":
    run()
