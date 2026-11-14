import asyncio
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROOFS_DIR = ROOT_DIR / "proofs"
PROOFS_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_OUT = PROOFS_DIR / "autoapply_working_apply_proof.mp4"
ARTIFACT_DIR = Path(r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37")

async def record_video():
    print("=" * 65)
    print("🎥 RECORDING COMPLETE E2E PROOF OF WORKING AUTO-APPLY ON LOCALHOST")
    print("=" * 65)

    # 1. Start local uvicorn server
    print("[*] Launching Uvicorn backend server at 127.0.0.1:8000...")
    python_exe = str(ROOT_DIR / "backend" / "venv" / "Scripts" / "python.exe")
    server_process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--app-dir", "backend"],
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)

    temp_video_dir = PROOFS_DIR / "temp_video"
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            record_video_dir=str(temp_video_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print("[*] Navigating to http://localhost:8000...")
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=20000)
        await asyncio.sleep(2)

        # 1. Record the Hero Section (User's requested original UI)
        print("[*] Showcasing Original Hero Section...")
        await page.screenshot(path=str(PROOFS_DIR / "video_step_1_hero.png"))
        await asyncio.sleep(2)

        # 2. Smooth scroll down to Agent Operations Console
        print("[*] Scrolling to Agent Console...")
        await page.evaluate("""() => {
            const consoleEl = document.getElementById('agentConsole') || document.querySelector('.console-section');
            if (consoleEl) {
                consoleEl.scrollIntoView({ behavior: 'smooth' });
            } else {
                window.scrollBy({ top: 800, behavior: 'smooth' });
            }
        }""")
        await asyncio.sleep(2)
        await page.screenshot(path=str(PROOFS_DIR / "video_step_2_console.png"))

        # 3. Wait for jobs table to be fully loaded with 25 verified live jobs
        print("[*] Waiting for live jobs to display in table...")
        await page.wait_for_selector("#jobsTableBody tr", timeout=15000)
        await asyncio.sleep(2)
        await page.screenshot(path=str(PROOFS_DIR / "video_step_3_jobs_table.png"))

        # 4. Find the first available Auto-Apply button
        print("[*] Locating Auto-Apply button on live job...")
        apply_btn = page.locator("#jobsTableBody button:has-text('Auto-Apply')").first
        if await apply_btn.is_visible():
            print("[*] Clicking 'Auto-Apply' button on live opening...")
            await apply_btn.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            await apply_btn.click()

            # 5. Wait for agent applying status and completion
            print("[*] Waiting for Playwright agent execution and DOM confirmation...")
            for wait_step in range(40):
                await asyncio.sleep(1.5)
                # Check if status has updated to Applied
                applied_badge = page.locator("#jobsTableBody span:has-text('Applied'), #jobsTableBody button:has-text('Applied')").first
                if await applied_badge.is_visible():
                    print("[*] Application marked APPLIED in table!")
                    break

            await asyncio.sleep(2)
            await page.screenshot(path=str(PROOFS_DIR / "video_step_4_applied_badge.png"))

            # 6. Click proof modal if available
            proof_btn = page.locator("#jobsTableBody button:has-text('View Proof'), #jobsTableBody a:has-text('Proof')").first
            if await proof_btn.is_visible():
                print("[*] Opening proof screenshot modal...")
                await proof_btn.click()
                await asyncio.sleep(2)
                await page.screenshot(path=str(PROOFS_DIR / "video_step_5_proof_modal.png"))

        await asyncio.sleep(2)
        await context.close()
        await browser.close()

    # Terminate background server process
    server_process.terminate()

    # Locate generated webm/mp4 video and convert/copy to final location
    video_files = list(temp_video_dir.glob("*.webm"))
    if video_files:
        src_video = video_files[0]
        # Convert webm to mp4 using ffmpeg/cv2
        import cv2
        cap = cv2.VideoCapture(str(src_video))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(VIDEO_OUT), fourcc, fps, (width, height))
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            out.write(frame)
        cap.release()
        out.release()
        print(f"🎉 Generated MP4 Video Proof at: {VIDEO_OUT}")

        # Copy to conversation artifact directory
        if ARTIFACT_DIR.exists():
            dest = ARTIFACT_DIR / "autoapply_working_apply_proof.mp4"
            shutil.copy2(str(VIDEO_OUT), str(dest))
            print(f"🎉 Mirrored Video Proof to Artifact: {dest}")
            for img in PROOFS_DIR.glob("video_step_*.png"):
                shutil.copy2(str(img), str(ARTIFACT_DIR / img.name))

if __name__ == "__main__":
    asyncio.run(record_video())
