import asyncio
import json
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, r"D:\ai-job-agent\backend")

from app.agents.naukri_live_runner import naukri_live_runner, check_naukri_application_count, verify_naukri_session
from app.agents.naukri_apply_agent import naukri_apply_agent

async def test_all():
    print("==================================================")
    print("Testing Real Naukri Submission & Session Integrity")
    print("==================================================")

    # Test 1: Missing cookies
    print("\n[Test 1] Missing cookies verification...")
    res_no_cookies = await naukri_live_runner.apply_single_job(
        job_url="https://www.naukri.com/job-listings-ai-engineer-12345",
        job_title="AI Engineer",
        user_id="non_existent_user_9999"
    )
    print("Result with no cookies:", res_no_cookies)
    assert res_no_cookies["status"] == "session_required", f"Expected session_required, got {res_no_cookies['status']}"
    print("[PASS] Test 1: Returns session_required when no cookies connected.")

    # Test 2: Dummy / Expired cookies session check
    print("\n[Test 2] Dummy cookies session verification...")
    dummy_cookies = [
        {"name": "_naukri_id", "value": "nk_dummy_val", "domain": ".naukri.com", "path": "/"},
        {"name": "naukri_session", "value": "auth_sess_fake_123", "domain": ".naukri.com", "path": "/"}
    ]
    is_valid, msg = await verify_naukri_session(dummy_cookies)
    print(f"Session check: is_valid={is_valid}, msg='{msg}'")
    assert not is_valid, "Dummy cookies should NOT be valid!"
    print("[PASS] Test 2: Dummy cookies correctly recognized as invalid/expired.")

    # Test 3: apply_single_job with dummy cookies
    print("\n[Test 3] apply_single_job with dummy cookies (MUST NOT claim applied_successfully)...")
    test_user_id = "test_qa_runner_123"
    cookie_dir = os.path.join(r"D:\ai-job-agent\backend\data\cookies", test_user_id)
    os.makedirs(cookie_dir, exist_ok=True)
    cookie_path = os.path.join(cookie_dir, "naukri_cookies.json")
    with open(cookie_path, "w", encoding="utf-8") as f:
        json.dump(dummy_cookies, f)

    res_dummy = await naukri_live_runner.apply_single_job(
        job_url="https://www.naukri.com/job-listings-ai-engineer-12345",
        job_title="AI Engineer",
        user_id=test_user_id
    )
    print("Result with dummy cookies:", res_dummy)
    assert res_dummy["status"] == "session_expired", f"Expected session_expired, got {res_dummy['status']}"
    assert res_dummy["status"] != "applied_successfully", "CRITICAL ERROR: Fake success returned!"
    print("[PASS] Test 3: apply_single_job rejects dummy cookies with session_expired.")

    # Test 4: naukri_apply_agent.apply_to_job with dummy cookies
    print("\n[Test 4] naukri_apply_agent.apply_to_job (MUST NOT simulate applied_successfully)...")
    agent_res = await naukri_apply_agent.apply_to_job(
        job_title="AI Engineer",
        company="Tech Recruiter",
        job_url="https://www.naukri.com/job-listings-ai-engineer-12345",
        user_id=test_user_id
    )
    print("Apply agent result:", agent_res)
    assert agent_res["status"] == "session_expired", f"Expected session_expired, got {agent_res['status']}"
    assert agent_res["status"] != "applied_successfully", "CRITICAL ERROR: Fake success returned by agent!"
    print("[PASS] Test 4: naukri_apply_agent NEVER simulates applied_successfully.")

    # Test 5: check_naukri_application_count with dummy cookies
    print("\n[Test 5] check_naukri_application_count helper...")
    count_res = await check_naukri_application_count(user_id=test_user_id)
    print("Count check result:", count_res)
    assert count_res["status"] == "session_expired", f"Expected session_expired, got {count_res['status']}"
    assert count_res["count"] is None, "Count should be None for expired session"
    print("[PASS] Test 5: check_naukri_application_count helper correctly flags session_expired.")

    # Test 6: check_naukri_application_count with no cookies
    print("\n[Test 6] check_naukri_application_count with no cookies...")
    count_no_cookies = await check_naukri_application_count(user_id="user_with_no_cookies")
    print("Count no cookies result:", count_no_cookies)
    assert count_no_cookies["status"] == "session_required", f"Expected session_required, got {count_no_cookies['status']}"
    print("[PASS] Test 6: check_naukri_application_count requires session when no cookies.")

    # Clean up test cookie dir
    try:
        os.remove(cookie_path)
        os.rmdir(cookie_dir)
    except Exception:
        pass

    # Test 7: Verify FastAPI route registration in main.py
    print("\n[Test 7] Verifying main.py FastAPI routes...")
    from main import app
    route_paths = [r.path for r in app.routes]
    print(f"Registered routes count: {len(route_paths)}")
    assert "/api/naukri/applied-count" in route_paths, "Route /api/naukri/applied-count missing!"
    assert "/api/naukri/auto-apply-live" in route_paths, "Route /api/naukri/auto-apply-live missing!"
    assert "/api/naukri/apply-single" in route_paths, "Route /api/naukri/apply-single missing!"
    print("[PASS] Test 7: All Naukri live application routes properly registered.")

    print("\n==================================================")
    print("ALL 7 NAUKRI LIVE SUBMISSION INTEGRITY TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_all())
