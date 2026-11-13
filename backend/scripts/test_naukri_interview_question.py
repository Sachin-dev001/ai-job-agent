import asyncio
from playwright.async_api import async_playwright

MOCK_NAUKRI_INTERVIEW_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Python Developer | GenAI | LLM | RAG - Infosys - Naukri.com</title>
</head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>Python Developer | GenAI | LLM | RAG - Infosys</h1>
    <div class="apply-button-container">
        <button id="apply-button" class="apply-button" style="padding: 10px 20px; background: #0073e6; color: white;">Apply</button>
    </div>

    <!-- Naukri Chatbot Drawer exactly as shown in user's video frame_006.png -->
    <div id="drawer" style="display: none; position: fixed; right: 0; top: 0; width: 380px; height: 100vh; background: white; box-shadow: -2px 0 10px rgba(0,0,0,0.1); padding: 20px; box-sizing: border-box;" class="chatbot_DrawerContentWrapper">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px;">
            <h3>Infosys Recruiter Bot</h3>
            <span style="cursor: pointer;">✕</span>
        </div>

        <div style="margin-top: 20px;">
            <p style="font-weight: bold; font-size: 14px; color: #333;">Are you available for a interview?(Virtual)</p>
            <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 15px;">
                <div class="radio-label" style="border: 1px solid #ddd; padding: 12px; border-radius: 8px; cursor: pointer;">
                    <label style="cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        <input type="radio" name="virtual_interview" value="yes"> Yes
                    </label>
                </div>
                <div class="radio-label" style="border: 1px solid #ddd; padding: 12px; border-radius: 8px; cursor: pointer;">
                    <label style="cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        <input type="radio" name="virtual_interview" value="no"> No
                    </label>
                </div>
            </div>
        </div>

        <!-- Bottom Action Bar (disabled until Yes is chosen, exactly like Naukri) -->
        <div style="position: absolute; bottom: 20px; left: 20px; right: 20px;" class="drawer-action-container">
            <button id="bottomSubmitBtn" style="width: 100%; padding: 12px; background: #b0d4ff; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: not-allowed;" disabled>
                Submit Application
            </button>
        </div>
    </div>

    <div id="confirmationBanner" style="display: none; padding: 20px; background: #d4edda; color: #155724; border-radius: 8px; margin-top: 20px;">
        <h3>You have successfully applied to Python Developer at Infosys</h3>
        <p>Application sent to recruiter on Naukri.com</p>
    </div>

    <script>
        document.getElementById("apply-button").addEventListener("click", () => {
            console.log("[MOCK NAUKRI] Apply button clicked, opening drawer...");
            document.getElementById("drawer").style.display = "block";
        });

        const radios = document.querySelectorAll("input[name='virtual_interview']");
        const submitBtn = document.getElementById("bottomSubmitBtn");

        radios.forEach(r => {
            r.addEventListener("change", () => {
                console.log("[MOCK NAUKRI] Radio changed to:", r.value);
                if (r.value === "yes") {
                    submitBtn.disabled = false;
                    submitBtn.style.background = "#0073e6";
                    submitBtn.style.cursor = "pointer";
                }
            });
        });

        submitBtn.addEventListener("click", () => {
            console.log("[MOCK NAUKRI] Submit Application clicked!");
            document.getElementById("drawer").style.display = "none";
            document.getElementById("confirmationBanner").style.display = "block";
        });
    </script>
</body>
</html>
"""

async def test_virtual_interview_flow():
    async with async_playwright() as p:
        print("[TEST] Launching browser to test exact virtual interview screening question...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        logs = []
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[ERROR] {e}"))

        await page.set_content(MOCK_NAUKRI_INTERVIEW_HTML)

        # Inject fixed content_naukri.js
        with open(r"D:\ai-job-agent\extension\content_naukri.js", "r", encoding="utf-8") as f:
            script_code = f.read()

        print("[TEST] Injecting fixed content_naukri.js ...")
        await page.add_script_tag(content=script_code)

        # Wait for robot execution: scan -> click Apply -> answer Yes -> click Submit
        await asyncio.sleep(10.0)

        for l in logs:
            print("  ", l)

        # 1. Check if YES radio was selected
        yes_checked = await page.locator("input[value='yes']").is_checked()
        print(f"[TEST] 'Yes' radio checked: {yes_checked}")
        assert yes_checked, "Expected 'Yes' radio to be checked!"

        # 2. Check if submission confirmation banner is visible
        confirmed = await page.locator("#confirmationBanner").is_visible()
        print(f"[TEST] Confirmation banner visible: {confirmed}")
        assert confirmed, "Expected confirmation banner to be visible!"

        print("\n==========================================")
        print("🎉 VIRTUAL INTERVIEW SCREENING QUESTION TEST PASSED 100%!")
        print("==========================================")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_virtual_interview_flow())
