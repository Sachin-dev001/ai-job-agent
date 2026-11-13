import os
import sys
import json
import asyncio

sys.path.insert(0, r"D:\ai-job-agent\backend")

from app.agents.naukri_live_runner import naukri_live_runner

async def main():
    print("Testing Naukri Live Runner on real opening...")
    # Load cookies
    cookies = naukri_live_runner._load_cookies(user_id="default")
    print(f"Loaded {len(cookies)} cookies for session.")
    
    # Test on a verified direct job listing
    job_url = "https://www.naukri.com/job-listings-gen-ai-full-stack-developer-pwc-hyderabad-gurugram-bengaluru-4-to-8-years-271026029882"
    result = await naukri_live_runner.apply_single_job(
        job_url=job_url,
        job_title="Gen AI Full Stack Developer",
        company="PwC",
        user_id="default"
    )
    print("Execution Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
