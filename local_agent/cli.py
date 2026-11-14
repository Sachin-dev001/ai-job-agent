import os
import sys
import asyncio
import argparse
from local_agent.browser_manager import LocalBrowserManager
from local_agent.session_setup import run_session_setup
from local_agent.naukri_applier import LocalNaukriApplier
from local_agent.wellfound_applier import LocalWellfoundApplier
from local_agent.linkedin_applier import LocalLinkedInApplier
from local_agent.yc_applier import LocalYCApplier
from local_agent.job_scout import LocalJobScout
from local_agent.config import PROOFS_DIR, HEADLESS

def print_banner():
    print("""
==================================================================
  🤖 PERSONAL LOCAL JOB AGENT - NAUKRI & WELLFOUND
  100% Autonomous Playwright Automation | Direct Residential IP
==================================================================
""")

async def check_status():
    print("\n[*] Auditing saved browser sessions in local profile...")
    async with LocalBrowserManager(headless=True) as bm:
        cookies = await bm.context.cookies()
        naukri_c = [c['name'] for c in cookies if 'naukri' in c.get('domain', '')]
        wellfound_c = [c['name'] for c in cookies if 'wellfound' in c.get('domain', '') or 'angel' in c.get('domain', '')]
        linkedin_c = [c['name'] for c in cookies if 'linkedin' in c.get('domain', '')]
        yc_c = [c['name'] for c in cookies if 'workatastartup' in c.get('domain', '') or 'ycombinator' in c.get('domain', '')]

        print(f" - Naukri Status:     {'✅ Logged In' if len(naukri_c) >= 5 else '⚠️ Not Logged In'}")
        print(f" - Wellfound Status:  {'✅ Logged In' if len(wellfound_c) >= 2 else '⚠️ Not Logged In'}")
        print(f" - LinkedIn Status:   {'✅ Logged In' if len(linkedin_c) >= 2 else '⚠️ Not Logged In'}")
        print(f" - Y Combinator:      {'✅ Logged In' if len(yc_c) >= 1 else '⚠️ Not Logged In'}")
        print("==================================================================\n")

async def apply_single_url(url: str, headless: bool = False):
    print(f"\n[Agent] Preparing to apply to: {url}")
    print("[Agent] Launching browser window...")
    async with LocalBrowserManager(headless=headless) as bm:
        page = await bm.get_page()
        if "naukri.com" in url:
            applier = LocalNaukriApplier(page)
            res = await applier.apply_to_job(url)
        elif "wellfound.com" in url:
            applier = LocalWellfoundApplier(page)
            res = await applier.apply_to_job(url)
        elif "linkedin.com" in url:
            applier = LocalLinkedInApplier(page)
            res = await applier.apply_to_job(url)
        elif "workatastartup.com" in url or "ycombinator.com" in url:
            applier = LocalYCApplier(page)
            res = await applier.apply_to_job(url)
        else:
            print(f"[!] Unsupported portal URL: {url}")
            return

        print("\n" + "=" * 55)
        print(" RESULT SUMMARY:")
        print(f" Status:  {res.get('status')}")
        print(f" Role:    {res.get('job_title')}")
        print(f" Company: {res.get('company')}")
        print(f" Proof:   {res.get('proof_path')}")
        print("=" * 55 + "\n")

async def auto_scout_and_apply(keyword: str = "Python Developer", limit: int = 3, headless: bool = False):
    print(f"\n[Agent] Starting auto scout & apply for: '{keyword}' (Limit: {limit})")
    async with LocalBrowserManager(headless=headless) as bm:
        page = await bm.get_page()
        scout = LocalJobScout(page)
        
        naukri_jobs = await scout.scout_naukri(keyword=keyword, limit=limit)
        
        print(f"\n[*] Found {len(naukri_jobs)} jobs. Commencing autonomous submissions...")
        naukri_applier = LocalNaukriApplier(page)
        
        results = []
        for i, job in enumerate(naukri_jobs, 1):
            print(f"\n--- Job {i}/{len(naukri_jobs)}: {job['title']} at {job['company']} ---")
            res = await naukri_applier.apply_to_job(job['url'])
            results.append(res)
            await asyncio.sleep(3.0)

        print("\n" + "=" * 65)
        print(" 🎯 AUTO-APPLY RUN COMPLETED")
        print(f" Total Attempted: {len(results)}")
        successful = sum(1 for r in results if r.get('status') == 'applied_successfully')
        print(f" Successfully Applied: {successful}")
        print(f" Screenshots saved to: {PROOFS_DIR}")
        print("=" * 65 + "\n")

def interactive_menu():
    print_banner()
    print("Select an option:")
    print(" 1. 🔑 Setup Login Session (Log into Naukri & Wellfound once)")
    print(" 2. ⚡ Apply to a specific Job URL")
    print(" 3. 🚀 Auto-Scout & Auto-Apply to matching jobs")
    print(" 4. 📊 Check Login Status")
    print(" 5. 🚪 Exit")
    print("-" * 65)

    try:
        choice = input("Enter choice (1-5): ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    if choice == "1":
        asyncio.run(run_session_setup())
    elif choice == "2":
        url = input("Enter Naukri or Wellfound Job URL: ").strip()
        if url:
            asyncio.run(apply_single_url(url, headless=False))
    elif choice == "3":
        kw = input("Enter job title / keyword (default: 'Python Developer'): ").strip() or "Python Developer"
        count = input("How many jobs to apply to? (default: 3): ").strip() or "3"
        try:
            limit = int(count)
        except ValueError:
            limit = 3
        asyncio.run(auto_scout_and_apply(keyword=kw, limit=limit, headless=False))
    elif choice == "4":
        asyncio.run(check_status())
    else:
        print("Exiting.")

def main():
    parser = argparse.ArgumentParser(description="Personal Local Job Agent")
    parser.add_argument("--setup", action="store_true", help="Launch browser to log in to Naukri & Wellfound")
    parser.add_argument("--apply", type=str, help="Apply directly to a job URL")
    parser.add_argument("--auto", action="store_true", help="Scout and auto-apply to matching jobs")
    parser.add_argument("--keyword", type=str, default="Python Developer", help="Search keyword for auto apply")
    parser.add_argument("--limit", type=int, default=3, help="Max jobs to apply to")
    parser.add_argument("--status", action="store_true", help="Check session login status")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")

    args = parser.parse_args()

    if args.setup:
        asyncio.run(run_session_setup())
    elif args.status:
        asyncio.run(check_status())
    elif args.apply:
        asyncio.run(apply_single_url(args.apply, headless=args.headless))
    elif args.auto:
        asyncio.run(auto_scout_and_apply(keyword=args.keyword, limit=args.limit, headless=args.headless))
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
