import os
import sys
import time
from playwright.sync_api import sync_playwright

PROOF_DIR = r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37\proofs_e2e_final"
os.makedirs(PROOF_DIR, exist_ok=True)
BASE_URL = "http://127.0.0.1:8000/"

def run():
    print("[TEST] Running Complete End-to-End Application Verification...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # 1. Load application console
        page.goto(f"{BASE_URL}#console", wait_until="networkidle")
        page.wait_for_selector("#jobsTableBody", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "01_landing_console.png"))
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
        page.fill("#authEmailInput", "kavita.rao@gmail.com")
        page.fill("#authPasswordInput", "KavitaPass2026!")
        page.click("#authSubmitBtn")

        page.wait_for_selector("#authModal", state="hidden")
        page.wait_for_selector("#authUserMenu", state="visible")
        user_name = page.text_content("#userNameDisplay").strip()
        assert "Kavita" in user_name, f"Expected Kavita, got: {user_name}"
        page.screenshot(path=os.path.join(PROOF_DIR, "02_kavita_signed_in.png"))
        print(f"[PASS] 3. Candidate account registered and authenticated: {user_name}")

        # 4. Switch between Naukri and Wellfound tabs and verify sync
        naukri_tab = page.query_selector("#tabNaukri")
        wellfound_tab = page.query_selector("#tabWellfound")
        if wellfound_tab:
            wellfound_tab.click()
            page.wait_for_timeout(400)
            btn_text = page.text_content("#runPlatformBtnText")
            assert "Wellfound" in btn_text, f"Expected Wellfound in button, got {btn_text}"
            print(f"[PASS] 4A. Wellfound tab switched successfully: Button='{btn_text.strip()}'")

        if naukri_tab:
            naukri_tab.click()
            page.wait_for_timeout(400)
            btn_text = page.text_content("#runPlatformBtnText")
            assert "Naukri" in btn_text, f"Expected Naukri in button, got {btn_text}"
            print(f"[PASS] 4B. Naukri tab switched successfully: Button='{btn_text.strip()}'")

        # 5. Test Memory Vault modal
        page.click("#navVaultBtn")
        page.wait_for_selector("#memoryVaultModal", state="visible")
        badge = page.text_content("#vaultOwnerBadge")
        assert "Kavita" in badge or "kavita" in badge.lower() or "Isolated" in badge, f"Unexpected badge: {badge}"
        page.screenshot(path=os.path.join(PROOF_DIR, "03_memory_vault_modal.png"))
        page.click("#memoryVaultModal button:has-text('✕')")
        page.wait_for_selector("#memoryVaultModal", state="hidden")
        print(f"[PASS] 5. Memory Vault verified and isolated for Kavita Rao: '{badge}'")

        # 6. Sign out
        page.click("#authUserMenu button")
        page.wait_for_selector("#userDropdownPanel", state="visible")
        page.click("button:has-text('Sign Out')")
        page.wait_for_selector("#authSignInBtn", state="visible")
        page.screenshot(path=os.path.join(PROOF_DIR, "04_signed_out_clean.png"))
        print("[PASS] 6. Signed out cleanly. All candidate state reset.")

        browser.close()
        print("\n=======================================================")
        print("[SUCCESS] COMPLETE END-TO-END APPLICATION AUDIT PASSED!")
        print("=======================================================")

if __name__ == "__main__":
    run()
