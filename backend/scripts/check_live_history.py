import json
import asyncio
from playwright.async_api import async_playwright

with open(r'D:\ai-job-agent\backend\cookies\fresh_naukri_cookies.json', 'r') as f:
    cookies = json.load(f)

async def check_history():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            channel="chrome",
            args=[
                "--headless=new",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        await context.add_init_script("delete Object.getPrototypeOf(navigator).webdriver; window.navigator.chrome = { runtime: {} };")
        
        clean_cookies = []
        for c in cookies:
            clean_cookies.append({
                "name": str(c["name"]).strip(),
                "value": str(c["value"]).strip(),
                "domain": str(c.get("domain", ".naukri.com")).strip(),
                "path": str(c.get("path", "/")).strip()
            })
            
        await context.add_cookies(clean_cookies)
        page = await context.new_page()
        
        print("Navigating to https://www.naukri.com/myapply/historypage with fresh session...")
        res = await page.goto("https://www.naukri.com/myapply/historypage", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3500)
        
        print("Status:", res.status if res else "None")
        print("Page URL:", page.url)
        print("Page Title:", await page.title())
        
        proof_path = r"D:\ai-job-agent\proofs\history_page_fresh_cookies.png"
        await page.screenshot(path=proof_path, full_page=True)
        print(f"Screenshot saved to {proof_path}")

        # Extract applications count and items
        info = await page.evaluate("""
            () => {
                const totalText = document.body.innerText;
                const matches = totalText.match(/Applied jobs \\((\\d+)\\)/i) || totalText.match(/(\\d+)\\s+Applied/i) || totalText.match(/Applications?\\s*\\((\\d+)\\)/i);
                
                const titles = [];
                document.querySelectorAll('.title, .designation, [class*=\"title\"], [class*=\"job-title\"]').forEach(el => {
                    const t = el.innerText.trim();
                    if (t.length > 3 && !titles.includes(t)) titles.push(t);
                });

                return {
                    detectedCountMatch: matches ? matches[0] : null,
                    countNumber: matches ? matches[1] : null,
                    titlesFound: titles.slice(0, 10),
                    bodySnippet: totalText.slice(0, 800)
                };
            }
        """)
        
        print("History Info:")
        print("  Detected Count:", info["detectedCountMatch"])
        print("  Count Number:", info["countNumber"])
        print("  Recent Job Titles:", info["titlesFound"])
        print("  Body Snippet:\n", info["bodySnippet"][:400])
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_history())
