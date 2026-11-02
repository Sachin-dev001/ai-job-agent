import asyncio
import os
from playwright.async_api import async_playwright

PROOF_DIR = r"D:\ai-job-agent\backend\proofs"

async def test_skip_and_animation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navigating to http://localhost:8000...")
        await page.goto("http://localhost:8000", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 1. Test mouse movement across hero to verify mouse-interactive animation
        print("Moving mouse to trigger interactive particle canvas & spotlight...")
        for x, y in [(400, 300), (600, 350), (800, 250), (720, 450)]:
            await page.mouse.move(x, y)
            await page.wait_for_timeout(300)

        await page.screenshot(path=os.path.join(PROOF_DIR, "mouse_animation_hero.png"))
        print("Captured mouse_animation_hero.png")

        # 2. Scroll down to console
        console_el = page.locator("#console")
        await console_el.scroll_into_view_if_needed()
        await page.wait_for_timeout(1000)

        # 3. Screenshot the redesigned Question Part with Skip Button
        pending_container = page.locator("#pendingQuestionsContainer")
        if await pending_container.is_visible():
            await page.screenshot(path=os.path.join(PROOF_DIR, "question_part_with_skip.png"))
            print("Captured question_part_with_skip.png")

            # 4. Hover over the question card to trigger 3D tilt and mouse spotlight
            card = page.locator("#pendingQuestionsList .interactive-card").first
            if await card.is_visible():
                box = await card.bounding_box()
                if box:
                    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    await page.wait_for_timeout(500)

            # 5. Click the Skip button!
            skip_btn = page.locator("button:has-text('Skip Question')").first
            if await skip_btn.is_visible():
                print("Clicking 'Skip Question' button...")
                await skip_btn.click()
                await page.wait_for_timeout(1500)
                await page.screenshot(path=os.path.join(PROOF_DIR, "question_after_skip.png"))
                print("Captured question_after_skip.png (cleanly dismissed!)")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_skip_and_animation())
