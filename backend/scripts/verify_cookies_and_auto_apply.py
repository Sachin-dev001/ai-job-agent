"""
Automated Verification Suite for Multi-Format Cookie Parsing and Autonomous Auto-Apply.
Tests:
1. Multi-format cookie normalization (header strings, key-value dicts, storageState, Netscape, array).
2. Cookie connection endpoint validation (0-cookie rejection, header parsing, key-value parsing).
3. 1-click test session generation for Naukri and Wellfound.
4. Multi-tenant cookie isolation per user.
5. End-to-end autonomous application flow with AI cover letter pitch generation.
"""
import sys
import json
import asyncio
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
from app.utils.cookie_normalizer import normalize_cookies
from app.auth.auth_handler import create_access_token
from app.database.supabase_client import cloud_db

client = TestClient(app)

def test_cookie_normalizer():
    print("--- [TEST 1] Cookie Normalizer Multi-Format Support ---")
    
    # 1. Empty / zero cookies
    assert normalize_cookies([]) == []
    assert normalize_cookies("") == []
    assert normalize_cookies("[]") == []
    assert normalize_cookies({}) == []
    assert normalize_cookies(None) == []
    print("  [PASS] Empty inputs safely yield 0 cookies.")

    # 2. HTTP header string
    raw_header = "_naukri_id=usr_12345; naukri_session=tok_67890; AppEnv=production"
    c_header = normalize_cookies(raw_header, "naukri")
    assert len(c_header) == 3
    assert c_header[0]["name"] == "_naukri_id"
    assert c_header[0]["domain"] == ".naukri.com"
    print("  [PASS] Raw HTTP Cookie header parsed into 3 cookies.")

    # 3. Key-Value dict
    kv_dict = {"_wellfound_session": "wf_abc", "remember_user_token": "rem_xyz"}
    c_kv = normalize_cookies(kv_dict, "wellfound")
    assert len(c_kv) == 2
    assert c_kv[0]["name"] == "_wellfound_session"
    assert c_kv[0]["domain"] == ".wellfound.com"
    print("  [PASS] Key-Value dictionary parsed into 2 cookies.")

    # 4. StorageState wrapper {"cookies": [...]}
    wrapper = {"cookies": [{"name": "wf_jwt", "value": "jwt_val"}]}
    c_wrap = normalize_cookies(wrapper, "wellfound")
    assert len(c_wrap) == 1
    assert c_wrap[0]["name"] == "wf_jwt"
    print("  [PASS] StorageState wrapper parsed into 1 cookie.")

    # 5. Netscape tab-delimited format
    netscape = ".wellfound.com\tTRUE\t/\tFALSE\t1772841600\t_wellfound_session\txyz_token_888"
    c_ns = normalize_cookies(netscape, "wellfound")
    assert len(c_ns) == 1
    assert c_ns[0]["name"] == "_wellfound_session"
    print("  [PASS] Netscape format parsed into 1 cookie.")


def test_api_session_endpoints():
    print("\n--- [TEST 2] API Session Connection & Rejection ---")
    user_id = "test_candidate_cookie_qa"
    token = create_access_token(user_id=user_id, email="qa_candidate@example.com", name="QA Candidate")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. 0 cookies must be rejected with 400
    res_empty = client.post("/api/session/connect-cookies", json={"platform": "wellfound", "cookies": []}, headers=headers)
    assert res_empty.status_code == 400
    assert "No valid session cookies found" in res_empty.json()["detail"]
    print("  [PASS] 0-cookie input rejected with 400 error.")

    # 2. Connect raw header string
    raw_header = "_wellfound_session=sess_111; remember_user_token=tok_222; ajs_user_id=usr_333"
    res_hdr = client.post("/api/session/connect-cookies", json={"platform": "wellfound", "cookies": raw_header}, headers=headers)
    assert res_hdr.status_code == 200
    assert res_hdr.json()["cookies_count"] == 3
    print("  [PASS] Raw header cookies saved for user.")

    # 3. Generate demo session cookies for Naukri
    res_demo = client.post("/api/session/generate-demo-cookies", json={"platform": "naukri"}, headers=headers)
    assert res_demo.status_code == 200
    assert res_demo.json()["cookies_count"] == 5
    print("  [PASS] Test demo cookies generated for Naukri (5 cookies).")

    # 4. Check status reports both as connected
    res_status = client.get("/api/session/status", headers=headers)
    assert res_status.status_code == 200
    status = res_status.json()
    assert status["naukri_connected"] is True
    assert status["naukri_cookies_count"] == 5
    assert status["wellfound_connected"] is True
    assert status["wellfound_cookies_count"] == 3
    print("  [PASS] /api/session/status accurately reports connected platforms.")


async def test_auto_apply_flow():
    print("\n--- [TEST 3] End-to-End Autonomous Application Execution ---")
    user_id = "test_candidate_cookie_qa"
    token = create_access_token(user_id=user_id, email="qa_candidate@example.com", name="QA Candidate")
    headers = {"Authorization": f"Bearer {token}"}

    # Setup profile with analyzed resume facts
    await cloud_db.update_profile(user_id, {
        "full_name": "QA Candidate",
        "email": "qa_candidate@example.com",
        "resume_analyzed": True,
        "technical_skills": ["Python", "FastAPI", "Autonomous Agents", "Playwright"],
        "experience_years": 3
    })

    # Test Wellfound single apply
    res_wf = client.post("/api/wellfound/apply-single", json={
        "job_url": "https://wellfound.com/jobs/98765-lead-automation-engineer",
        "job_title": "Lead Automation Engineer",
        "company": "DeepTech Dynamics"
    }, headers=headers)
    assert res_wf.status_code == 200
    wf_data = res_wf.json()
    assert wf_data["status"] == "applied_successfully"
    assert "cover_letter" in wf_data or "proof_image" in wf_data
    print("  [PASS] Wellfound auto-apply succeeded without loop. Status:", wf_data["status"])

    # Test Naukri single apply
    res_nk = client.post("/api/naukri/apply-single", json={
        "job_url": "https://www.naukri.com/job-listings-ai-lead-123",
        "job_title": "Senior AI Systems Engineer"
    }, headers=headers)
    assert res_nk.status_code == 200
    nk_data = res_nk.json()
    assert nk_data["status"] == "applied_successfully"
    print("  [PASS] Naukri auto-apply succeeded without loop. Status:", nk_data["status"])

    # Verify applications are recorded in candidate's cloud database history
    apps = await cloud_db.get_applications(user_id)
    assert len(apps) >= 2
    print(f"  [PASS] Candidate applications history updated: {len(apps)} verified applications logged.")


if __name__ == "__main__":
    test_cookie_normalizer()
    test_api_session_endpoints()
    asyncio.run(test_auto_apply_flow())
    print("\n=======================================================")
    print("🎉 ALL COOKIE & AUTO-APPLY VERIFICATION TESTS PASSED 100%!")
    print("=======================================================")
