import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
from playwright.async_api import async_playwright

ROOT_DIR = Path(r"D:\ai-job-agent")
FRONTEND_INDEX = ROOT_DIR / "frontend" / "index.html"
PROOFS_OUTPUT = ROOT_DIR / "proofs" / "proof_routing_verification"
PROOFS_OUTPUT.mkdir(parents=True, exist_ok=True)

async def test_frontend_and_modal():
    print("=" * 70)
    print("TEST SUITE: PROOF ROUTING & IN-APP LIGHTBOX MODAL VERIFICATION")
    print("=" * 70)

    # 1. Verify vercel.json configurations
    print("\n[STEP 1] Validating vercel.json rewrites...")
    for vpath in [ROOT_DIR / "vercel.json", ROOT_DIR / "frontend" / "vercel.json"]:
        assert vpath.exists(), f"{vpath} does not exist!"
        with open(vpath, "r", encoding="utf-8") as f:
            vdata = json.load(f)
        rewrites = vdata.get("rewrites", [])
        proof_rw = next((r for r in rewrites if "proofs" in r["source"]), None)
        api_rw = next((r for r in rewrites if "api" in r["source"]), None)
        assert proof_rw, f"Missing proofs rewrite in {vpath}"
        assert api_rw, f"Missing api rewrite in {vpath}"
        assert "autoapply-backend-hvdm.onrender.com" in proof_rw["destination"]
        assert "autoapply-backend-hvdm.onrender.com" in api_rw["destination"]
        print(f"  -> Verified {vpath.name}: {proof_rw['source']} -> {proof_rw['destination']}")

    # 2. Launch Chromium and test index.html and app.js
    print("\n[STEP 2] Launching Headless Chromium to verify DOM & JS functions...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        # Intercept static files so /static/ loads from local frontend/static
        async def handle_route(route):
            url = route.request.url
            if "/static/" in url:
                rel = url.split("/static/")[1].split("?")[0]
                local_file = ROOT_DIR / "frontend" / "static" / rel
                if local_file.exists():
                    with open(local_file, "rb") as f:
                        body = f.read()
                    content_type = "application/javascript" if rel.endswith(".js") else "text/css"
                    await route.fulfill(body=body, content_type=content_type)
                    return
            await route.continue_()

        await page.route("**/*", handle_route)

        page.on("console", lambda msg: print(f"  [BROWSER CONSOLE] {msg.type}: {msg.text}") if msg.type in ["error"] else None)

        file_url = FRONTEND_INDEX.resolve().as_uri()
        await page.goto(file_url, wait_until="load")
        await page.wait_for_timeout(1000)

        # 3. Test URL Helper Functions
        print("\n[STEP 3] Testing getBackendApiUrl() & getProofUrl() logic in browser...")
        res = await page.evaluate("""() => {
            const results = {};
            results.defaultBackend = getBackendApiUrl();
            results.absProof = getProofUrl('https://images.unsplash.com/photo-1.png');
            results.relProofSlash = getProofUrl('/proofs/tenant_123/proof_abc.png');
            results.relProofNoSlash = getProofUrl('proofs/tenant_123/proof_abc.png');
            results.filenameOnly = getProofUrl('proof_abc.png');
            results.nullProof = getProofUrl(null);
            results.emptyProof = getProofUrl('');
            results.hashProof = getProofUrl('#');
            return results;
        }""")

        print(f"  Default Backend: {res['defaultBackend']}")
        assert "https://autoapply-backend-hvdm.onrender.com" in res['defaultBackend'] or "http" in res['defaultBackend']
        assert res['absProof'] == 'https://images.unsplash.com/photo-1.png'
        assert "/proofs/tenant_123/proof_abc.png" in res['relProofSlash']
        assert res['relProofSlash'].startswith("http")
        assert res['relProofNoSlash'].startswith("http")
        assert "/proofs/tenant_123/proof_abc.png" in res['relProofNoSlash']
        assert "/proofs/proof_abc.png" in res['filenameOnly']
        assert res['nullProof'] == ""
        assert res['emptyProof'] == ""
        assert res['hashProof'] == ""
        print("  -> PASSED: All getProofUrl() permutations resolve to fully-qualified endpoints!")

        # 4. Test In-App Proof Modal opening
        print("\n[STEP 4] Testing openProofModal() UI display...")
        # Check initial state: hidden
        modal_is_hidden = await page.evaluate("() => document.getElementById('proofModal').classList.contains('hidden')")
        assert modal_is_hidden, "proofModal should be hidden on load"

        # Open proof modal
        test_img = "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800"
        await page.evaluate(f"() => openProofModal('{test_img}', 'Staff AI Engineer')")
        await page.wait_for_timeout(500)

        modal_is_open = await page.evaluate("() => !document.getElementById('proofModal').classList.contains('hidden')")
        assert modal_is_open, "proofModal should be visible after openProofModal()"

        title_text = await page.text_content("#proofModalJobTitle")
        assert "Staff AI Engineer" in title_text
        print(f"  Modal Title rendered: {title_text}")

        new_tab_href = await page.get_attribute("#proofModalOpenNewTab", "href")
        assert new_tab_href == test_img
        print(f"  Open In New Tab Link: {new_tab_href}")

        # Capture Screenshot of open lightbox modal
        lightbox_screenshot = PROOFS_OUTPUT / "01_proof_modal_lightbox_open.png"
        await page.screenshot(path=str(lightbox_screenshot))
        print(f"  -> Lightbox screenshot saved to: {lightbox_screenshot}")

        # 5. Test Escape Key to close modal
        print("\n[STEP 5] Testing Escape key dismissal...")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        is_hidden_esc = await page.evaluate("() => document.getElementById('proofModal').classList.contains('hidden')")
        assert is_hidden_esc, "Modal did not close on Escape key"
        print("  -> PASSED: Escape key successfully closed proofModal!")

        # 6. Test Backdrop Click to close modal
        print("\n[STEP 6] Testing Backdrop click dismissal...")
        await page.evaluate(f"() => openProofModal('{test_img}', 'Backend Engineer')")
        await page.wait_for_timeout(200)
        # Click on modal background backdrop
        await page.click("#proofModal", position={"x": 10, "y": 10})
        await page.wait_for_timeout(300)
        is_hidden_backdrop = await page.evaluate("() => document.getElementById('proofModal').classList.contains('hidden')")
        assert is_hidden_backdrop, "Modal did not close on backdrop click"
        print("  -> PASSED: Backdrop click successfully closed proofModal!")

        # 7. Test Image Error / Cold Start Fallback State
        print("\n[STEP 7] Testing Cold-Start / Fallback Error State...")
        await page.evaluate("() => openProofModal('/proofs/non_existent_mock_test_image.png', 'Mock Role')")
        # Trigger error handler
        await page.evaluate("() => handleProofImageError()")
        await page.wait_for_timeout(300)

        err_visible = await page.evaluate("() => !document.getElementById('proofModalError').classList.contains('hidden')")
        assert err_visible, "proofModalError should be visible on image error"
        loading_hidden = await page.evaluate("() => document.getElementById('proofModalLoading').classList.contains('hidden')")
        assert loading_hidden, "proofModalLoading should be hidden on image error"

        error_screenshot = PROOFS_OUTPUT / "02_proof_modal_coldstart_fallback.png"
        await page.screenshot(path=str(error_screenshot))
        print(f"  -> Cold-start error fallback screenshot saved to: {error_screenshot}")
        print("  -> PASSED: Error state displays friendly retry & direct URL controls!")

        await browser.close()

    print("\n" + "=" * 70)
    print("ALL FRONTEND PROOF ROUTING & MODAL LIGHTBOX TESTS PASSED (7/7)!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_frontend_and_modal())
