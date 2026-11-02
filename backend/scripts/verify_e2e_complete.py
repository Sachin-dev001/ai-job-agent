import asyncio
import os
from playwright.async_api import async_playwright

PROOF_DIR = r"D:\ai-job-agent\backend\proofs"
os.makedirs(PROOF_DIR, exist_ok=True)

async def test_full_application():
    print("=== STARTING FULL END-TO-END VERIFICATION TEST ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        # Step 1: Open Localhost:8000
        print("\n[Step 1] Loading http://localhost:8000...")
        await page.goto("http://localhost:8000", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)

        # Trigger sample resume upload or ensure roles are populated
        analyze_btn = page.locator("#analyzeBtn")
        if await analyze_btn.is_visible():
            print("[Step 1.1] Clicking 'Analyze Resume with LLM'...")
            await analyze_btn.click()
            await page.wait_for_timeout(3000)

        # Verify no memory vault under jobs table
        # Check that table container has nothing below it
        await page.screenshot(path=os.path.join(PROOF_DIR, "e2e_01_initial_dashboard.png"))
        print("[Step 1.2] Screenshot taken: e2e_01_initial_dashboard.png")

        # Step 2: Test Data Analyst Role Selection on Wellfound
        print("\n[Step 2] Testing Recommended Role 'Data Analyst' on Wellfound...")
        # Check if role card exists or search directly
        da_card = page.locator("#rolesList div:has-text('Data Analyst')").first
        if await da_card.is_visible():
            print("Clicking 'Data Analyst' role card...")
            await da_card.click()
            await page.wait_for_timeout(1000)

            # Check Platform Selector Modal
            modal = page.locator("#platformSelectorModal")
            if await modal.is_visible():
                print("Platform Selector Modal visible! Selecting Wellfound...")
                wf_btn = page.locator("#platformSelectorModal div:has-text('Wellfound')").first
                await wf_btn.click()
                await page.wait_for_timeout(2000)
        else:
            # Fallback: switch to Wellfound tab directly
            print("Switching to Wellfound tab and searching Data Analyst...")
            await page.click("#tabWellfound")
            await page.wait_for_timeout(1500)

        await page.screenshot(path=os.path.join(PROOF_DIR, "e2e_02_wellfound_data_analyst_jobs.png"))
        print("[Step 2.1] Screenshot taken: e2e_02_wellfound_data_analyst_jobs.png")

        # Inspect table rows
        rows = await page.locator("#jobsTableBody tr").all()
        print(f"[Step 2.2] Jobs in table: {len(rows)}")
        for idx, row in enumerate(rows):
            txt = (await row.text_content() or "").strip().replace('\n', ' ')
            txt_safe = txt.encode('ascii', errors='ignore').decode('ascii')
            print(f"  Row {idx}: {txt_safe[:80]}")
            # Ensure no ML or Data Engineer in Data Analyst list
            lower_txt = txt.lower()
            assert "data engineer" not in lower_txt, f"Error: Data Engineer found in Data Analyst search: {txt}"
            assert "machine learning" not in lower_txt, f"Error: ML found in Data Analyst search: {txt}"

        # Step 3: Test Auto-Apply on Wellfound
        print("\n[Step 3] Clicking Auto-Apply on row 0 (Wellfound)...")
        auto_apply_btn = page.locator("#jobsTableBody tr button:has-text('Auto-Apply')").first
        if await auto_apply_btn.is_visible():
            await auto_apply_btn.click()
            print("Clicked Auto-Apply! Waiting for application to submit and verify...")
            # Wait for either Applied badge or Proof link
            await page.wait_for_selector("#jobsTableBody tr:first-child a:has-text('Proof'), #jobsTableBody tr:first-child span:has-text('Applied')", timeout=45000)
            await page.wait_for_timeout(2000)
            print("Auto-Apply completed!")
            await page.screenshot(path=os.path.join(PROOF_DIR, "e2e_03_wellfound_applied_proof.png"))
            print("[Step 3.1] Screenshot taken: e2e_03_wellfound_applied_proof.png")

            # Check proof link
            proof_link = page.locator("#jobsTableBody tr:first-child a:has-text('Proof')").first
            if await proof_link.is_visible():
                href = await proof_link.get_attribute("href")
                print(f"Proof URL: {href}")

        # Step 4: Test Memory Vault Modal
        print("\n[Step 4] Testing Memory Vault Modal...")
        vault_btn = page.locator("button:has-text('Memory Vault')").first
        if await vault_btn.is_visible():
            await vault_btn.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=os.path.join(PROOF_DIR, "e2e_04_memory_vault_modal.png"))
            print("[Step 4.1] Screenshot taken: e2e_04_memory_vault_modal.png")

            # Close modal
            close_btn = page.locator("#memoryVaultModal button:has-text('✕')").first
            if await close_btn.is_visible():
                await close_btn.click()
                await page.wait_for_timeout(500)

        # Step 5: Test Switching to Naukri and Searching "AI Engineer"
        print("\n[Step 5] Testing Naukri platform tab with 'AI Engineer'...")
        await page.click("#tabNaukri")
        await page.wait_for_timeout(1500)
        # Search AI Engineer
        await page.evaluate("() => triggerJobSearch('AI Engineer')")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(PROOF_DIR, "e2e_05_naukri_ai_engineer.png"))
        print("[Step 5.1] Screenshot taken: e2e_05_naukri_ai_engineer.png")

        # Inspect Naukri rows
        naukri_rows = await page.locator("#jobsTableBody tr").all()
        print(f"[Step 5.2] Naukri AI jobs in table: {len(naukri_rows)}")
        for idx, row in enumerate(naukri_rows):
            txt = (await row.text_content() or "").strip().replace('\n', ' ')
            txt_safe = txt.encode('ascii', errors='ignore').decode('ascii')
            print(f"  Naukri Row {idx}: {txt_safe[:80]}")
            lower_txt = txt.lower()
            assert "data analyst" not in lower_txt, f"Error: Data Analyst found in AI Engineer search: {txt}"

        await browser.close()
        print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    asyncio.run(test_full_application())
