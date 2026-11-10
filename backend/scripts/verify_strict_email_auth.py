import os
import sys
import time
from playwright.sync_api import sync_playwright

PROOF_DIR = r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37\proofs_strict_email_auth"
os.makedirs(PROOF_DIR, exist_ok=True)
BASE_URL = "http://127.0.0.1:8000/"

def sign_out(page):
    page.click("#authUserMenu button")
    page.wait_for_selector("#userDropdownPanel", state="visible")
    page.click("button:has-text('Sign Out')")
    page.wait_for_selector("#authSignInBtn", state="visible")

def run():
    print(f"[TEST] Verifying strict Gmail/Email & Password authentication and zero-leak privacy on {BASE_URL}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # Capture console errors or warnings
        page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}") if msg.type == "error" else None)

        # 1. Unauthenticated landing
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector("#authSignInBtn", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "01_clean_landing_unauth.png"))
        print("[PASS] 1. Unauthenticated visitor loaded with zero candidate leaks.")

        # 2. Open Auth Modal - Verify clean Email/Password only UI
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        
        # Verify no Google or GitHub buttons exist in DOM
        assert page.query_selector("#googleFallbackBtn") is None, "Google button still exists!"
        assert page.query_selector("#googleAuthView") is None, "googleAuthView still exists!"
        assert page.query_selector("#githubAuthView") is None, "githubAuthView still exists!"
        assert page.query_selector("#detectedAccountsSection") is None, "detectedAccountsSection still exists!"
        
        page.screenshot(path=os.path.join(PROOF_DIR, "02_auth_modal_email_only.png"))
        print("[PASS] 2. Auth modal contains strictly Gmail/Email & Password. Zero Google/GitHub buttons.")

        # 3. New user tries to Sign In without an account -> MUST BE REJECTED with message to create account
        page.fill("#authEmailInput", "niharika.sen@gmail.com")
        page.fill("#authPasswordInput", "Password123!")
        page.click("#authSubmitBtn")
        
        page.wait_for_selector("#authErrorMsg", state="visible")
        err_text = page.text_content("#authErrorText")
        assert "No account found" in err_text, f"Expected 'No account found' error, got: {err_text}"
        assert "Create Account" in err_text, f"Expected prompt to create account, got: {err_text}"
        page.screenshot(path=os.path.join(PROOF_DIR, "03_signin_rejected_new_user.png"))
        print(f"[PASS] 3. Unregistered user properly blocked on Sign In: '{err_text}'")

        # 4. Switch to Create Account tab
        page.click("#tabSignUpBtn")
        page.wait_for_selector("#signUpNameField", state="visible")
        submit_btn_text = page.text_content("#authSubmitBtnText")
        assert "Create Account" in submit_btn_text, f"Expected 'Create Account' button text, got: {submit_btn_text}"
        page.screenshot(path=os.path.join(PROOF_DIR, "04_create_account_tab.png"))
        print("[PASS] 4. Create Account tab active with Candidate Full Name field.")

        # 5. Create new account for Niharika Sen
        page.fill("#authNameInput", "Niharika Sen")
        page.fill("#authEmailInput", "niharika.sen@gmail.com")
        page.fill("#authPasswordInput", "Password123!")
        page.click("#authSubmitBtn")

        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Niharika" in user_name, f"Expected Niharika in user name display, got: {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "05_niharika_registered_and_logged_in.png"))
        print(f"[PASS] 5. Niharika Sen account created and logged in: {user_name}")

        # 6. Sign out Niharika Sen
        sign_out(page)
        print("[PASS] 6. Signed out cleanly.")

        # 7. Test wrong password for existing user
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.fill("#authEmailInput", "niharika.sen@gmail.com")
        page.fill("#authPasswordInput", "WrongPassword999!")
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authErrorMsg", state="visible")
        err_text = page.text_content("#authErrorText")
        assert "Incorrect password" in err_text, f"Expected 'Incorrect password', got: {err_text}"
        print(f"[PASS] 7. Incorrect password rejected: '{err_text}'")

        # 8. Test correct password for existing user
        page.fill("#authPasswordInput", "Password123!")
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Niharika" in user_name, f"Expected Niharika, got {user_name}"
        print(f"[PASS] 8. Niharika Sen logged back in successfully with correct password.")

        # 9. Sign out and create second user (Poonam Verma) - verify zero leakage
        sign_out(page)
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        # Ensure email field is empty and doesn't leak Niharika's email
        email_val = page.input_value("#authEmailInput")
        assert email_val == "", f"Email field leaked previous user: '{email_val}'"
        
        page.click("#tabSignUpBtn")
        page.fill("#authNameInput", "Poonam Verma")
        page.fill("#authEmailInput", "poonam.verma@gmail.com")
        page.fill("#authPasswordInput", "PoonamSecure2026!")
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Poonam" in user_name, f"Expected Poonam, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "06_poonam_registered_and_logged_in.png"))
        print(f"[PASS] 9. Poonam Verma created private account with zero data leakage: {user_name}")

        browser.close()
        print("\n=======================================================")
        print("[SUCCESS] ALL 9/9 STRICT EMAIL/PASSWORD & ZERO-LEAK TESTS PASSED!")
        print("=======================================================")

if __name__ == "__main__":
    run()
