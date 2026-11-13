import asyncio
from playwright.async_api import async_playwright

MOCK_WELLFOUND_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>AI Engineer at stealth startup - Wellfound</title>
</head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>AI Engineer - Stealth AI Startup</h1>
    <div class="apply-container">
        <button id="applyBtn" style="padding: 10px 20px; background: #e02424; color: white;">Apply</button>
    </div>

    <!-- Wellfound Modal -->
    <div id="modal" style="display: none; border: 1px solid #ccc; padding: 20px; margin-top: 20px; max-width: 500px;">
        <h3>Apply to Stealth AI Startup</h3>
        <div>
            <label>Why are you interested in this role?</label><br>
            <textarea name="userNote" placeholder="Write a note to the hiring team..." style="width: 100%; height: 100px;"></textarea>
        </div>
        <div style="margin-top: 15px;">
            <label>Do you require visa sponsorship?</label><br>
            <label><input type="radio" name="visa" value="yes"> Yes</label>
            <label><input type="radio" name="visa" value="no"> No</label>
        </div>
        <div style="margin-top: 15px;">
            <label>Years of experience with Python/LLMs:</label><br>
            <input type="text" name="exp" style="width: 100%;">
        </div>
        <div style="margin-top: 20px;">
            <button id="sendBtn" style="padding: 10px 20px; background: #000; color: white;">Send Application</button>
        </div>
    </div>

    <div id="successMsg" style="display: none; color: green; font-weight: bold; margin-top: 20px;">
        Application submitted successfully on Wellfound!
    </div>

    <script>
        document.getElementById("applyBtn").addEventListener("click", () => {
            console.log("[MOCK WELLFOUND] Apply clicked!");
            document.getElementById("modal").style.display = "block";
        });
        document.getElementById("sendBtn").addEventListener("click", () => {
            console.log("[MOCK WELLFOUND] Send Application clicked!");
            document.getElementById("modal").style.display = "none";
            document.getElementById("successMsg").style.display = "block";
        });
    </script>
</body>
</html>
"""

async def test_wellfound():
    async with async_playwright() as p:
        print("[TEST] Testing Wellfound auto-apply flow...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        logs = []
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[ERROR] {e}"))

        await page.set_content(MOCK_WELLFOUND_HTML)

        with open(r"D:\ai-job-agent\extension\content_wellfound.js", "r", encoding="utf-8") as f:
            script = f.read()

        print("[TEST] Injecting content_wellfound.js ...")
        await page.add_script_tag(content=script)

        await asyncio.sleep(7.0)

        for l in logs:
            print("  ", l)

        # 1. Note was filled
        note_val = await page.locator("textarea[name='userNote']").input_value()
        print(f"[TEST] Recruiter Note filled (length {len(note_val)}): {note_val[:60]}...")
        assert len(note_val) > 20, "Expected recruiter note to be filled!"

        # 2. Sponsorship radio "No" was checked
        no_checked = await page.locator("input[value='no']").is_checked()
        print(f"[TEST] Sponsorship 'No' radio checked: {no_checked}")
        assert no_checked, "Expected sponsorship 'No' to be checked!"

        # 3. Success message visible
        is_success = await page.locator("#successMsg").is_visible()
        print(f"[TEST] Wellfound success confirmation visible: {is_success}")
        assert is_success, "Expected Wellfound success confirmation to be visible!"

        print("\n==========================================")
        print("🎉 WELLFOUND AUTO-APPLY TEST PASSED 100%!")
        print("==========================================")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_wellfound())
