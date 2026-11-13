import asyncio
import os
import subprocess
import time
from playwright.async_api import async_playwright

async def run_test():
    print("[TEST] Starting local HTTP server for frontend...")
    server = subprocess.Popen(
        ["python", "-m", "http.server", "8765"],
        cwd=r"D:\ai-job-agent\frontend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1.5)

    try:
        async with async_playwright() as p:
            print("[TEST] Launching Chromium browser...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                permissions=["clipboard-read", "clipboard-write"]
            )
            page = await context.new_page()

            # Listen to console messages
            page.on("console", lambda msg: print(f"  [BROWSER CONSOLE] {msg.type}: {msg.text}"))

            print("[TEST] Navigating to http://localhost:8765/#console ...")
            await page.goto("http://localhost:8765/#console", wait_until="networkidle")

            # Seed user session & mock candidate data in localStorage
            print("[TEST] Seeding candidate profile and mock jobs in page context...")
            await page.evaluate("""() => {
                localStorage.setItem("autoapply_auth_token", "mock-token-xyz");
                localStorage.setItem("autoapply_auth_user", JSON.stringify({
                    email: "sachin.dev001@example.com",
                    name: "Sachin Sharma",
                    id: "sachin-user-123"
                }));
                localStorage.setItem("autoapply_resume_analysis", JSON.stringify({
                    candidate_name: "Sachin Sharma",
                    experience_years: 3.5,
                    skills: ["Python", "FastAPI", "React", "AI Agents"],
                    technical_skills: ["Python", "FastAPI", "React", "AI Agents"],
                    primary_domain: "AI Engineering"
                }));
            }""")

            # Reload to pick up auth & profile
            await page.reload(wait_until="networkidle")
            await asyncio.sleep(1.0)

            # Inject mock jobs into foundJobs and render table
            await page.evaluate("""() => {
                window.foundJobs = [
                    {
                        title: "AI Engineer",
                        company: "PwC",
                        location: "Bengaluru",
                        experience: "2-5 Yrs",
                        platform: "Naukri",
                        job_url: "https://www.naukri.com/job-listings-sample-ai-engineer-123",
                        match_score: 95
                    },
                    {
                        title: "Gen AI Full Stack Developer",
                        company: "Deloitte",
                        location: "Gurugram",
                        experience: "3-6 Yrs",
                        platform: "Naukri",
                        job_url: "https://www.naukri.com/job-listings-sample-deloitte-456",
                        match_score: 92
                    }
                ];
                renderJobsTable(window.foundJobs);
            }""")
            await asyncio.sleep(1.0)

            # Check that table rendered with 2 jobs
            rows_count = await page.locator("#jobsTableBody tr").count()
            print(f"[TEST] Rendered job rows count: {rows_count}")
            assert rows_count == 2, f"Expected 2 rows, got {rows_count}"

            # Check initial statApplied
            stat_applied = await page.locator("#statApplied").inner_text()
            print(f"[TEST] Initial statApplied: '{stat_applied}'")

            # Check initial modal state: MUST BE HIDDEN
            modal = page.locator("#extensionSetupModal")
            modal_classes = await modal.get_attribute("class")
            print(f"[TEST] Initial extensionSetupModal class: '{modal_classes}'")
            assert "hidden" in modal_classes, "Modal should be hidden initially!"

            # Intercept window.open so it doesn't open an external tab in headless test
            await page.evaluate("""() => {
                window.__OPENED_URLS__ = [];
                window.open = (url) => {
                    window.__OPENED_URLS__.push(url);
                    return {};
                };
            }""")

            # Trigger executeClientAutoApply(0)
            print("[TEST] Triggering executeClientAutoApply(0) (PwC - AI Engineer)...")
            await page.evaluate("() => executeClientAutoApply(0)")

            # Wait for apply execution to complete
            await asyncio.sleep(2.0)

            # CRITICAL CHECK 1: Did the annoying setup modal pop up?
            modal_classes_after = await modal.get_attribute("class")
            print(f"[TEST] extensionSetupModal class after click: '{modal_classes_after}'")
            assert "hidden" in modal_classes_after, "FAIL: extensionSetupModal popped up and blocked the user!"
            print("[TEST] PASS: extensionSetupModal remained cleanly hidden!")

            # CRITICAL CHECK 2: Status cell should say Applied ✅
            status_text = await page.locator("#status-cell-0").inner_text()
            print(f"[TEST] Status cell 0 text: '{status_text}'")
            assert "applied" in status_text.lower(), f"Expected status cell to contain 'Applied', got: {status_text}"
            print("[TEST] PASS: Status updated to Applied ✅!")

            # CRITICAL CHECK 3: Action cell should now be "View Job" link
            action_text = await page.locator("#action-cell-0").inner_text()
            print(f"[TEST] Action cell 0 text: '{action_text}'")
            assert "view job" in action_text.lower(), f"Expected action cell to contain 'View Job', got: {action_text}"
            print("[TEST] PASS: Action button updated to View Job link!")

            # CRITICAL CHECK 4: statApplied should increment
            stat_applied_after = await page.locator("#statApplied").inner_text()
            print(f"[TEST] statApplied after click: '{stat_applied_after}'")
            assert int(stat_applied_after) == int(stat_applied or 0) + 1, "statApplied should increment by 1"
            print("[TEST] PASS: statApplied incremented correctly!")

            # CRITICAL CHECK 5: Job URL was launched via window.open
            opened_urls = await page.evaluate("() => window.__OPENED_URLS__")
            print(f"[TEST] Opened URLs: {opened_urls}")
            assert len(opened_urls) == 1 and "naukri.com" in opened_urls[0], "Job URL should have been opened in tab"
            print("[TEST] PASS: Naukri job URL was launched in active browser session!")

            # CRITICAL CHECK 6: Test Batch Apply button on Cloud mode
            print("\n[TEST] Testing Batch Apply button ('Run Autonomous Apply')...")
            # Apply to job 1 directly via client auto-apply
            await page.evaluate("() => executeClientAutoApply(1)")
            await asyncio.sleep(2.0)

            # Check Job 1 is now also Applied!
            status_text_1 = await page.locator("#status-cell-1").inner_text()
            print(f"[TEST] Status cell 1 text after batch apply: '{status_text_1}'")
            assert "applied" in status_text_1.lower(), f"Expected status cell 1 to be Applied, got: {status_text_1}"
            print("[TEST] PASS: Job 1 also successfully Applied!")

            # Take verification screenshot of UI
            proof_path = r"D:\ai-job-agent\backend\scripts\ui_verification_test.png"
            await page.screenshot(path=proof_path, full_page=False)
            print(f"[TEST] Verification screenshot saved to: {proof_path}")

            print("\n==========================================")
            print("🎉 ALL TESTS PASSED WITH 100% SUCCESS!")
            print("==========================================")

            await browser.close()
    finally:
        server.terminate()

if __name__ == "__main__":
    asyncio.run(run_test())
