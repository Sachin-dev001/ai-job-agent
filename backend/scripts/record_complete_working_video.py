import os
import sys
import time
import asyncio
import cv2
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

import uvicorn
import multiprocessing
from playwright.async_api import async_playwright

def run_local_backend():
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def convert_webm_to_mp4(webm_path: str, mp4_path: str, frame_out_dir: str):
    print(f"\n[Video Converter] Converting {webm_path} to MP4...")
    cap = cv2.VideoCapture(webm_path)
    if not cap.isOpened():
        print(f"[Video Converter] Warning: could not open {webm_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(mp4_path, fourcc, fps, (width, height))

    os.makedirs(frame_out_dir, exist_ok=True)
    frame_idx = 0
    saved_frames = 0
    interval = max(1, int(fps * 1.2)) # every 1.2 seconds

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        if frame_idx % interval == 0:
            frame_file = os.path.join(frame_out_dir, f"proof_frame_{saved_frames:03d}.png")
            cv2.imwrite(frame_file, frame)
            saved_frames += 1
        frame_idx += 1

    cap.release()
    out.release()
    print(f"[Video Converter] 🎉 MP4 Video created: {mp4_path} ({frame_idx} frames, {saved_frames} frames saved to {frame_out_dir})")

async def record_full_video():
    video_dir = ROOT_DIR / "proofs" / "video_recordings"
    video_dir.mkdir(parents=True, exist_ok=True)
    frame_dir = ROOT_DIR / "proofs" / "final_video_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(" 🎥 RECORDING COMPREHENSIVE E2E VIDEO OF ORIGINAL UI & PLAYWRIGHT AGENT")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 720}
        )

        page = await context.new_page()
        page.on("dialog", lambda d: asyncio.create_task(d.accept()))

        # ======================================================================
        # SCENE 1: Original UI Hero Section on http://127.0.0.1:8000
        # ======================================================================
        print("[Scene 1] Loading Original UI on http://127.0.0.1:8000 ...")
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3.0)

        # Highlight navbar
        await page.hover("#navUserBtn, [id*='user']")
        await asyncio.sleep(1.5)

        # ======================================================================
        # SCENE 2: Scroll to Agent Operations Console
        # ======================================================================
        print("[Scene 2] Clicking 'Launch Agent Console ↓' button...")
        launch_btn = page.locator("a:has-text('Launch Agent Console'), button:has-text('Launch Agent Console')").first
        if await launch_btn.is_visible():
            await launch_btn.click()
            await asyncio.sleep(2.5)

        # ======================================================================
        # SCENE 3: Inspect Candidate DNA and Live Jobs Table
        # ======================================================================
        print("[Scene 3] Inspecting Candidate DNA & Live Naukri Openings...")
        await page.locator("#jobsTableBody").scroll_into_view_if_needed()
        await asyncio.sleep(2.0)

        # Hover over first row
        first_row = page.locator("#jobsTableBody tr").first
        if await first_row.is_visible():
            await first_row.hover()
            await asyncio.sleep(1.5)

        # ======================================================================
        # SCENE 4: Click Auto-Apply on first job
        # ======================================================================
        print("[Scene 4] Clicking 'Auto-Apply' button on GenAI Developer role...")
        apply_btn = page.locator("button:has-text('Auto-Apply')").first
        if await apply_btn.is_visible():
            await apply_btn.click()
            print("[Scene 4] Auto-Apply initiated! Agent navigating and executing...")
            
            # Allow agent time to execute and update status
            for i in range(12):
                await asyncio.sleep(1.0)
                status_text = (await page.locator("#status-cell-0, .status-cell").first.text_content() or "").lower()
                if "applied" in status_text:
                    print(f"[Scene 4] Status updated: {status_text.strip()}!")
                    break

        await asyncio.sleep(3.0)

        # ======================================================================
        # SCENE 5: Open Submission Proof Modal
        # ======================================================================
        print("[Scene 5] Opening verified submission proof modal...")
        proof_btn = page.locator("a:has-text('Proof'), button:has-text('Proof')").first
        if await proof_btn.is_visible():
            await proof_btn.click()
            await asyncio.sleep(3.5)

        # Close proof modal if open
        close_modal_btn = page.locator("#proofModal button, [onclick*='closeProofModal']").first
        if await close_modal_btn.is_visible():
            await close_modal_btn.click()
            await asyncio.sleep(1.5)

        # Close page & finalize video
        await page.close()
        raw_video = await page.video.path()
        await context.close()
        await browser.close()

        print(f"[Raw Video] Captured to: {raw_video}")

        # Convert to final MP4
        final_mp4 = str(ROOT_DIR / "proofs" / "autoapply_project_working_proof.mp4")
        convert_webm_to_mp4(raw_video, final_mp4, str(frame_dir))

        # Copy to conversation artifacts
        target_brain_dir = Path(r"C:\Users\t\.gemini\antigravity\brain\b7d99792-53e9-42d3-bcfa-08b775d98d37")
        if target_brain_dir.exists():
            import shutil
            shutil.copy2(final_mp4, target_brain_dir / "autoapply_project_working_proof.mp4")
            for f in frame_dir.glob("*.png"):
                shutil.copy2(f, target_brain_dir / f.name)
            print(f"[Artifacts] Video and frames mirrored to {target_brain_dir}")

        print("\n" + "=" * 70)
        print(" 🎉 FULL E2E VIDEO PROOF RECORDED & READY!")
        print("=" * 70 + "\n")

if __name__ == "__main__":
    server_proc = multiprocessing.Process(target=run_local_backend, daemon=True)
    server_proc.start()
    time.sleep(3.0)

    try:
        asyncio.run(record_full_video())
    finally:
        server_proc.terminate()
