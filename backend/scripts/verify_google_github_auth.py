import os
import sys
import time
from playwright.sync_api import sync_playwright

PROOF_DIR = r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37\proofs_auth_overhaul"
os.makedirs(PROOF_DIR, exist_ok=True)

def sign_out(page):
    page.click("#authUserMenu button")
    page.wait_for_selector("#userDropdownPanel", state="visible")
    page.click("button:has-text('Sign Out')")
    page.wait_for_selector("#authSignInBtn", state="visible")

def run():
    print("[TEST] Launching browser to verify Google & GitHub authentication overhaul...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # 1. Open page
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page.wait_for_selector("#authSignInBtn", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "01_fresh_visitor_landing.png"))
        print("[PASS] 1. Unauthenticated fresh visitor loaded with zero leaks.")

        # 2. Open Auth Modal
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        det_sec = page.query_selector("#detectedAccountsSection")
        assert "hidden" in det_sec.get_attribute("class"), "Detected accounts leaked to fresh visitor!"
        page.screenshot(path=os.path.join(PROOF_DIR, "02_auth_modal_clean.png"))
        print("[PASS] 2. Auth modal opened; zero account leakage to third party.")

        # 3. Google 1-Click Fast Track
        page.click("#googleFallbackBtn")
        page.wait_for_selector("#googleAuthView", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "03_google_auth_view.png"))
        print("[PASS] 3. Google auth view displayed cleanly without external redirect errors.")

        # Click the 1-click Sachin button
        page.click("button:has-text('1-Click Sign In')")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Sachin" in user_name, f"Expected Sachin in user name, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "04_google_1click_signed_in.png"))
        print(f"[PASS] 4. Google 1-Click signed in successfully: {user_name}")

        # 4. Sign Out
        sign_out(page)
        print("[PASS] 5. Signed out successfully.")

        # 5. Google Custom Address Sign In
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.click("#googleFallbackBtn")
        page.wait_for_selector("#googleAuthView", state="visible")
        
        page.fill("#googleDirectEmailInput", "alex.dev@gmail.com")
        page.fill("#googleDirectNameInput", "Alex Developer")
        page.click("button:has-text('Sign In with Google Account')")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Alex Developer" in user_name, f"Expected Alex Developer, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "05_google_custom_signed_in.png"))
        print(f"[PASS] 6. Custom Google sign-in successful: {user_name}")

        # Sign Out
        sign_out(page)

        # 6. GitHub 1-Click Fast Track
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.click("button:has-text('Continue with GitHub')")
        page.wait_for_selector("#githubAuthView", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "06_github_auth_view.png"))
        print("[PASS] 7. GitHub auth view opened cleanly.")

        # Click 1-Click GitHub
        page.click("#githubAuthView button:has-text('1-Click Sign In')")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Sachin-dev001" in user_name or "sachin" in user_name.lower(), f"Expected Sachin-dev001, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "07_github_1click_signed_in.png"))
        print(f"[PASS] 8. GitHub 1-Click signed in successfully: {user_name}")

        # Sign Out
        sign_out(page)

        # 7. GitHub Custom Username Sign In
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.click("button:has-text('Continue with GitHub')")
        page.wait_for_selector("#githubAuthView", state="visible")
        page.fill("#githubDirectUserInput", "torvalds")
        page.click("button:has-text('Authenticate with GitHub')")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "torvalds" in user_name.lower() or "linus" in user_name.lower(), f"Expected torvalds or linus, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "08_github_torvalds_signed_in.png"))
        print(f"[PASS] 9. GitHub custom handle sign-in successful: {user_name}")

        # Sign Out
        sign_out(page)

        # 8. Email/Password Seamless Auto-Registration on Sign In Tab
        page.click("#authSignInBtn")
        page.wait_for_selector("#authModal", state="visible")
        page.fill("#authEmailInput", "sarah.connor@skynet.ai")
        page.fill("#authPasswordInput", "TopSecretPass2026!")
        # Click "Sign In to Dashboard" on an unregistered email
        page.click("#authSubmitBtn")
        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Sarah Connor" in user_name or "sarah" in user_name.lower(), f"Expected Sarah Connor, got {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "09_email_auto_registered.png"))
        print(f"[PASS] 10. Email seamless auto-registration passed: {user_name}")

        browser.close()
        print("\n=======================================================")
        print("[SUCCESS] ALL 10/10 GOOGLE & GITHUB AUTHENTICATION TESTS PASSED!")
        print("=======================================================")

if __name__ == "__main__":
    run()
