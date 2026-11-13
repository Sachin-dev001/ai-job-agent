import asyncio
import sys
sys.path.insert(0, "D:/ai-job-agent/backend")
from app.auth.auth_handler import create_access_token
from playwright.async_api import async_playwright

valid_token = create_access_token("sachin.dev001@example.com", "sachin-dev001", name="Sachin Sharma")

async def run_live_test():
    async with async_playwright() as p:
        print("[LIVE TEST] Launching browser to test live Vercel deployment...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = await context.new_page()

        page.on("console", lambda m: print("  [CONSOLE]", m.type, m.text))
        page.on("pageerror", lambda e: print("  [PAGE ERROR]", e))

        live_url = "https://ai-job-agent-frontend-mauve.vercel.app/#console"
        print(f"[LIVE TEST] Navigating to {live_url} ...")
        await page.goto(live_url, wait_until="networkidle")

        # Set real valid auth and candidate profile in localStorage
        await page.evaluate(f"""() => {{
            localStorage.setItem("autoapply_auth_token", "{valid_token}");
            localStorage.setItem("autoapply_user", JSON.stringify({{
                email: "sachin.dev001@example.com",
                name: "Sachin Sharma",
                id: "sachin-dev001"
            }}));
            localStorage.setItem("autoapply_candidate_profile", JSON.stringify({{
                candidate_name: "Sachin Sharma",
                experience_years: 3.5,
                skills: ["Python", "FastAPI", "React", "AI Agents"],
                primary_domain: "AI Engineering"
            }}));
        }}""")

        await page.reload(wait_until="networkidle")
        await asyncio.sleep(1.5)

        # Mock jobs into table
        await page.evaluate("""() => {
            window.foundJobs = [
                {
                    title: "Gen AI Engineer",
                    company: "Tech Mahindra",
                    location: "Noida",
                    experience: "2-4 Yrs",
                    platform: "Naukri",
                    job_url: "https://www.naukri.com/job-listings-gen-ai-engineer-123",
                    match_score: 96
                }
            ];
            renderJobsTable(window.foundJobs);
        }""")
        await asyncio.sleep(1.0)

        # Intercept window.open
        await page.evaluate("""() => {
            window.__OPENED_URLS__ = [];
            window.open = (url) => { window.__OPENED_URLS__.push(url); return {}; };
        }""")

        # Find and click the Auto-Apply button inside #action-cell-0
        auto_apply_btn = page.locator("#action-cell-0 button", has_text="Auto-Apply")
        btn_onclick = await auto_apply_btn.get_attribute("onclick")
        print(f"[LIVE TEST] Auto-Apply button onclick attribute: '{btn_onclick}'")

        # Click Auto-Apply
        print("[LIVE TEST] Clicking Auto-Apply on live Vercel page...")
        await auto_apply_btn.click()
        # Wait for Status to become Applied ✅
        print("[LIVE TEST] Waiting for status cell to update to Applied ✅...")
        await page.wait_for_selector("#status-cell-0:has-text('Applied')", timeout=15000)
        status_text = await page.locator("#status-cell-0").inner_text()
        print(f"[LIVE TEST] Status cell text: '{status_text}'")
        assert "applied" in status_text.lower(), f"Expected status to be Applied, got: {status_text}"
        print("[LIVE TEST] PASS: Status updated to Applied ✅!")

        # Verify Action button changed to View Job
        action_text = await page.locator("#action-cell-0").inner_text()
        print(f"[LIVE TEST] Action cell text: '{action_text}'")
        assert "view job" in action_text.lower(), f"Expected action to be View Job, got: {action_text}"
        print("[LIVE TEST] PASS: Action button updated to View Job link!")

        # Verify URL was launched
        opened_urls = await page.evaluate("() => window.__OPENED_URLS__")
        print(f"[LIVE TEST] Launched URL: {opened_urls}")
        assert len(opened_urls) == 1 and "naukri.com" in opened_urls[0]
        print("[LIVE TEST] PASS: Job URL successfully launched!")

        # Take screenshot of live Vercel confirmation
        proof_path = r"D:\ai-job-agent\backend\scripts\live_vercel_verified.png"
        await page.screenshot(path=proof_path, full_page=False)
        print(f"[LIVE TEST] Verification screenshot saved to: {proof_path}")

        print("\n==========================================")
        print("🎉 LIVE VERCEL PRODUCTION TEST 100% PASSED!")
        print("==========================================")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_live_test())
