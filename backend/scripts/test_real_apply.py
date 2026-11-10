import asyncio
import json
import sys
sys.path.insert(0, "D:/ai-job-agent/backend")

from app.agents.naukri_live_runner import naukri_live_runner

async def test_apply():
    url = "https://www.naukri.com/job-listings-hiring-python-developer-in-chennai-allegis-group-chennai-5-to-10-years-101126008957"
    title = "Hiring Python Developer in Chennai !"
    company = "TEKsystems"

    print("Target job:", title, "at", company)
    print("URL:", url)

    with open("D:/ai-job-agent/backend/cookies/fresh_naukri_cookies.json", "r") as f:
        cookies = json.load(f)

    result = await naukri_live_runner.apply_single_job(
        job_url=url,
        job_title=title,
        company=company,
        user_id="user-c2FjaGluLnNoYXJtYS5lbmdpbmVlckBnbWFpbC5jb20",
        override_cookies=cookies
    )

    print("\n--- APPLY RESULT ---")
    print("Status:", result.get("status"))
    print("Message:", result.get("message"))
    print("Proof:", result.get("proof_image"))
    if "question_data" in result:
        print("Question Data:", result.get("question_data"))

if __name__ == "__main__":
    asyncio.run(test_apply())
