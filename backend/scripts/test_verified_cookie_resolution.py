import sys
sys.path.insert(0, "D:/ai-job-agent/backend")
import asyncio
from app.agents.naukri_live_runner import naukri_live_runner
from app.database.supabase_client import cloud_db

async def test_cookie_hierarchy():
    print("--- 1. Testing Default Cookie Loading ---")
    cookies = naukri_live_runner._load_cookies(user_id="random-new-user-12345")
    print(f"Loaded {len(cookies)} cookies for brand new user (via system fallback).")
    assert len(cookies) > 0, "Failed to load default cookies for new user!"

    print("\n--- 2. Testing Cloud DB Sync Resolution ---")
    cloud_c = cloud_db.get_cookies_sync("random-new-user-12345", "naukri")
    print(f"Cloud DB resolved {len(cloud_c)} cookies for new user via fallback.")
    assert len(cloud_c) > 0, "Cloud DB get_cookies_sync failed fallback!"

    print("\n--- 3. Testing verify_naukri_session ---")
    is_valid, msg = await naukri_live_runner.verify_naukri_session(cookies)
    print(f"Session valid: {is_valid}, msg: {msg}")

    print("\nALL COOKIE RESOLUTION TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_cookie_hierarchy())
