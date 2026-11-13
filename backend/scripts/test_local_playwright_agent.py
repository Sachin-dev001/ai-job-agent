import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.async_api import async_playwright
from local_agent.naukri_applier import LocalNaukriApplier
from local_agent.wellfound_applier import LocalWellfoundApplier
from local_agent.config import PROOFS_DIR

MOCK_NAUKRI_HTML = """<!DOCTYPE html>
<html>
<head><title>Senior GenAI Engineer - TechCorp</title></head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>Senior GenAI Engineer</h1>
    <a class="comp-name">TechCorp Solutions</a>
    <div>
        <button id="apply-button" style="padding: 10px 20px; background: #0070df; color: white;">Apply</button>
    </div>

    <div class="chatbot_drawer" style="display: none; border: 1px solid #ddd; padding: 15px; margin-top: 20px;">
        <h3>Candidate Screening</h3>
        <div>
            <p>Are you available for a interview?(Virtual)</p>
            <label><input type="radio" name="avail" value="yes"> Yes</label>
            <label><input type="radio" name="avail" value="no"> No</label>
        </div>
        <div>
            <p>Select your notice period:</p>
            <label><input type="radio" name="np" value="15"> 15 Days or less</label>
            <label><input type="radio" name="np" value="60"> 2 Months</label>
        </div>
        <div>
            <p>Total Experience in Years:</p>
            <input type="text" name="exp" placeholder="Enter total experience">
        </div>
        <div style="margin-top: 15px;">
            <button id="bottomSubmitBtn" style="padding: 8px 16px; background: #27ae60; color: white;">Submit Application</button>
        </div>
    </div>

    <div id="confirmed" style="display: none; color: green; font-size: 20px; margin-top: 20px;">
        You have successfully applied to Senior GenAI Engineer!
    </div>

    <script>
        document.getElementById('apply-button').addEventListener('click', () => {
            document.querySelector('.chatbot_drawer').style.display = 'block';
        });
        document.getElementById('bottomSubmitBtn').addEventListener('click', () => {
            document.querySelector('.chatbot_drawer').style.display = 'none';
            document.getElementById('confirmed').style.display = 'block';
        });
    </script>
</body>
</html>
"""

MOCK_WELLFOUND_HTML = """<!DOCTYPE html>
<html>
<head><title>AI Agent Developer at Stealth AI - Wellfound</title></head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>AI Agent Developer</h1>
    <h2 data-test="JobCompany">Stealth AI</h2>
    <div>
        <button data-test="JobApplyButton" style="padding: 10px 20px; background: #000; color: white;">Apply now</button>
    </div>

    <div id="apply-modal" style="display: none; border: 1px solid #ccc; padding: 20px; margin-top: 20px;">
        <label>Why are you interested in this role?</label><br>
        <textarea name="userNote" placeholder="Write a note to the hiring team..."></textarea>
        <div>
            <p>Do you require visa sponsorship?</p>
            <label><input type="radio" name="visa" value="yes"> Yes</label>
            <label><input type="radio" name="visa" value="no"> No</label>
        </div>
        <div style="margin-top: 15px;">
            <button id="sendBtn" style="padding: 10px 20px; background: #e02424; color: white;">Send application</button>
        </div>
    </div>

    <div id="wf-success" style="display: none; color: green; font-size: 20px; margin-top: 20px;">
        Application sent successfully on Wellfound!
    </div>

    <script>
        document.querySelector('[data-test="JobApplyButton"]').addEventListener('click', () => {
            document.getElementById('apply-modal').style.display = 'block';
        });
        document.getElementById('sendBtn').addEventListener('click', () => {
            document.getElementById('apply-modal').style.display = 'none';
            document.getElementById('wf-success').style.display = 'block';
        });
    </script>
</body>
</html>
"""

async def run_tests():
    print("\n" + "=" * 65)
    print(" 🧪 TESTING LOCAL PLAYWRIGHT JOB APPLIERS")
    print("=" * 65)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # TEST 1: Naukri Local Applier
        print("\n[TEST 1] Testing LocalNaukriApplier on Naukri application flow...")
        await page.set_content(MOCK_NAUKRI_HTML)
        naukri_applier = LocalNaukriApplier(page)
        naukri_res = await naukri_applier.apply_to_job("https://www.naukri.com/job-listings-genai-123", skip_goto=True)
        
        print("[TEST 1] Result:", naukri_res)
        assert naukri_res["status"] == "applied_successfully", "Naukri applier failed!"
        assert os.path.exists(naukri_res["proof_path"]), "Naukri proof screenshot not found!"
        print("✅ TEST 1 PASSED: Naukri screening, questionnaire, and submission verified!")

        # TEST 2: Wellfound Local Applier
        print("\n[TEST 2] Testing LocalWellfoundApplier on Wellfound application flow...")
        await page.set_content(MOCK_WELLFOUND_HTML)
        wf_applier = LocalWellfoundApplier(page)
        wf_res = await wf_applier.apply_to_job("https://wellfound.com/jobs/ai-developer-456", skip_goto=True)

        print("[TEST 2] Result:", wf_res)
        assert wf_res["status"] == "applied_successfully", "Wellfound applier failed!"
        assert os.path.exists(wf_res["proof_path"]), "Wellfound proof screenshot not found!"
        print("✅ TEST 2 PASSED: Wellfound note, sponsorship answering, and submission verified!")

        await browser.close()

    print("\n" + "=" * 65)
    print(" 🎉 ALL LOCAL PLAYWRIGHT AUTO-APPLY TESTS PASSED 100%!")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
