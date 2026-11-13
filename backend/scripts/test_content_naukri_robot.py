import asyncio
import os
from playwright.async_api import async_playwright

MOCK_NAUKRI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>AI Engineer at PwC - Naukri.com</title>
</head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>AI Engineer - PwC</h1>
    <div class="apply-button-container">
        <button id="apply-button" class="apply-button" style="padding: 10px 20px; background: #0073e6; color: white;">Apply</button>
    </div>

    <!-- Hidden Questionnaire Drawer that opens after apply click -->
    <div id="drawer" style="display: none; border: 1px solid #ccc; padding: 15px; margin-top: 20px;" class="chatbot_DrawerContentWrapper">
        <h3>Recruiter Questionnaire</h3>
        <div>
            <label>Notice Period:</label><br>
            <label><input type="radio" name="notice" value="15"> 15 Days or less</label><br>
            <label><input type="radio" name="notice" value="30"> 30 Days</label>
        </div>
        <div style="margin-top: 10px;">
            <label>Total Experience (Years):</label><br>
            <input type="text" name="experience" placeholder="Total Experience">
        </div>
        <div style="margin-top: 10px;">
            <label>Current CTC (Lacs):</label><br>
            <input type="text" name="current_ctc" placeholder="Current CTC">
        </div>
        <div style="margin-top: 10px;">
            <label>Expected CTC (Lacs):</label><br>
            <input type="text" name="expected_ctc" placeholder="Expected CTC">
        </div>
        <div style="margin-top: 15px;">
            <button id="drawerSubmitBtn" type="submit" style="padding: 8px 16px; background: #28a745; color: white;">Submit Application</button>
        </div>
    </div>

    <div id="confirmedMsg" style="display: none; color: green; font-weight: bold; margin-top: 20px;">
        You have already applied for this vacancy
    </div>

    <script>
        document.getElementById("apply-button").addEventListener("click", () => {
            console.log("[MOCK NAUKRI] Apply button physically clicked!");
            document.getElementById("drawer").style.display = "block";
        });
        document.getElementById("drawerSubmitBtn").addEventListener("click", (e) => {
            e.preventDefault();
            console.log("[MOCK NAUKRI] Drawer Submit button physically clicked!");
            document.getElementById("drawer").style.display = "none";
            document.getElementById("confirmedMsg").style.display = "block";
        });
    </script>
</body>
</html>
"""

async def run_robot_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Listen to console messages
        logs = []
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[UNCAUGHT ERROR] {e}"))

        # Set mock HTML
        await page.set_content(MOCK_NAUKRI_HTML)

        # Read fixed content_naukri.js
        with open(r"D:\ai-job-agent\extension\content_naukri.js", "r", encoding="utf-8") as f:
            script_code = f.read()

        # Inject and run content_naukri.js
        print("[ROBOT TEST] Injecting fixed content_naukri.js into page...")
        await page.add_script_tag(content=script_code)

        # Wait for robot execution (1.5s scan + click + drawer + submit)
        await asyncio.sleep(8.0)

        for log in logs:
            print("  ", log)

        # Verify drawer was submitted and confirmedMsg is displayed
        is_submitted = await page.locator("#confirmedMsg").is_visible()
        print(f"[ROBOT TEST] Submission confirmed on page: {is_submitted}")

        # Check notice period radio was checked
        radio_checked = await page.locator("input[value='15']").is_checked()
        print(f"[ROBOT TEST] Notice period '15 Days or less' checked: {radio_checked}")

        # Check experience was filled
        exp_val = await page.locator("input[name='experience']").input_value()
        print(f"[ROBOT TEST] Filled Experience: '{exp_val}'")

        assert is_submitted, "Expected submission confirmation to be visible!"
        assert radio_checked, "Expected 15-day notice period radio to be checked!"
        assert exp_val == "3.5", f"Expected experience to be '3.5', got '{exp_val}'"

        print("\n==========================================")
        print("🎉 ROBOT TEST PASSED WITH ZERO ERRORS!")
        print("==========================================")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_robot_test())
