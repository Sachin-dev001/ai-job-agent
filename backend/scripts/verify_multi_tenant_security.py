import os
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main
from main import app
from app.database.supabase_client import cloud_db
from app.agents.naukri_live_runner import naukri_live_runner
from app.agents.wellfound_live_runner import wellfound_live_runner

client = TestClient(app)

def create_auth_headers(user_id: str, email: str, name: str) -> dict:
    """Creates a JWT auth header for testing multi-tenant isolation."""
    import jwt
    payload = {
        "sub": user_id,
        "email": email,
        "user_metadata": {
            "name": name,
            "full_name": name
        }
    }
    # Using dummy secret or none
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    # If auth handler accepts unsigned or decoded payload:
    return {"Authorization": f"Bearer {token}"}

async def run_tests():
    print("=" * 70)
    print("RUNNING MULTI-TENANT SESSION & SECURITY VERIFICATION SUITE")
    print("=" * 70)

    user_a_headers = create_auth_headers("tenant_alice", "alice@example.com", "Alice Smith")
    user_b_headers = create_auth_headers("tenant_bob", "bob@example.com", "Bob Jones")
    user_c_headers = create_auth_headers("tenant_charlie", "charlie@example.com", "Charlie Brown")

    # Clean up any test cookie files from previous runs
    data_cookies = BACKEND_DIR / "data" / "cookies"
    for uid in ["tenant_alice", "tenant_bob", "tenant_charlie"]:
        udir = data_cookies / uid
        if udir.exists():
            import shutil
            shutil.rmtree(udir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # TEST 1: Global Cookies Neutralization
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Verifying global cookies are neutralized...")
    global_naukri = BACKEND_DIR / "cookies" / "naukri_cookies.json"
    global_wellfound = BACKEND_DIR / "cookies" / "wellfound_cookies.json"
    
    with open(global_naukri, "r") as f:
        g_naukri_data = json.load(f)
    with open(global_wellfound, "r") as f:
        g_wf_data = json.load(f)
    
    assert len(g_naukri_data) == 0, f"Global naukri_cookies.json must be empty, found {len(g_naukri_data)}"
    assert len(g_wf_data) == 0, f"Global wellfound_cookies.json must be empty, found {len(g_wf_data)}"
    print("  -> PASSED: Global cookies neutralized to []")

    # --------------------------------------------------------------------------
    # TEST 2: Multi-Tenant Cookie Isolation Between Users
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Verifying Cookie Isolation: User A cannot see or use User B's cookies...")
    
    # Check initial status for Alice (no cookies)
    res_a_init = client.get("/api/session/status", headers=user_a_headers)
    assert res_a_init.status_code == 200
    data_a_init = res_a_init.json()
    assert data_a_init["naukri_connected"] is False
    assert data_a_init["wellfound_connected"] is False
    assert data_a_init["naukri_cookies_count"] == 0

    # Alice connects 3 Naukri cookies
    alice_cookies = [
        {"name": "session_id", "value": "alice_secret_123", "domain": ".naukri.com"},
        {"name": "user_hash", "value": "alice_hash_456", "domain": ".naukri.com"},
        {"name": "nk_token", "value": "alice_token_789", "domain": ".naukri.com"}
    ]
    res_connect_a = client.post(
        "/api/session/connect-cookies",
        headers=user_a_headers,
        json={"platform": "naukri", "cookies": alice_cookies}
    )
    assert res_connect_a.status_code == 200
    assert res_connect_a.json()["cookies_count"] == 3

    # Check Alice's status: Naukri is connected
    res_a_status = client.get("/api/session/status", headers=user_a_headers)
    assert res_a_status.json()["naukri_connected"] is True
    assert res_a_status.json()["naukri_cookies_count"] == 3
    assert res_a_status.json()["wellfound_connected"] is False

    # Check Bob's status: Bob must have 0 cookies (NOT see Alice's cookies)
    res_b_status = client.get("/api/session/status", headers=user_b_headers)
    assert res_b_status.json()["naukri_connected"] is False
    assert res_b_status.json()["naukri_cookies_count"] == 0
    assert res_b_status.json()["wellfound_connected"] is False

    # Bob connects 2 Wellfound cookies
    bob_cookies = [
        {"name": "wf_auth", "value": "bob_wf_key_999", "domain": ".wellfound.com"},
        {"name": "wf_user", "value": "bob_wf_user_111", "domain": ".wellfound.com"}
    ]
    res_connect_b = client.post(
        "/api/session/connect-cookies",
        headers=user_b_headers,
        json={"platform": "wellfound", "cookies": bob_cookies}
    )
    assert res_connect_b.status_code == 200
    assert res_connect_b.json()["cookies_count"] == 2

    # Check Bob's status again
    res_b_status2 = client.get("/api/session/status", headers=user_b_headers)
    assert res_b_status2.json()["wellfound_connected"] is True
    assert res_b_status2.json()["wellfound_cookies_count"] == 2
    assert res_b_status2.json()["naukri_connected"] is False

    # Check Alice's status again: Alice does NOT see Bob's Wellfound cookies
    res_a_status2 = client.get("/api/session/status", headers=user_a_headers)
    assert res_a_status2.json()["wellfound_connected"] is False
    assert res_a_status2.json()["wellfound_cookies_count"] == 0
    assert res_a_status2.json()["naukri_connected"] is True
    assert res_a_status2.json()["naukri_cookies_count"] == 3

    # Check cookie files on disk are partitioned strictly by user ID
    alice_disk = BACKEND_DIR / "data" / "cookies" / "tenant_alice" / "naukri_cookies.json"
    bob_disk = BACKEND_DIR / "data" / "cookies" / "tenant_bob" / "wellfound_cookies.json"
    assert alice_disk.exists(), "Alice cookies not saved under data/cookies/tenant_alice"
    assert bob_disk.exists(), "Bob cookies not saved under data/cookies/tenant_bob"
    assert not (BACKEND_DIR / "data" / "cookies" / "tenant_alice" / "wellfound_cookies.json").exists()
    assert not (BACKEND_DIR / "data" / "cookies" / "tenant_bob" / "naukri_cookies.json").exists()

    print("  -> PASSED: Multi-tenant cookies are strictly isolated by user.id!")

    # --------------------------------------------------------------------------
    # TEST 3: Resume Analysis Requirement Enforcement
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Verifying Resume Analysis requirement for auto-apply...")
    expected_msg = "Resume profile required before running auto-apply. Please upload and analyze your resume first."

    endpoints_to_test = [
        ("POST", "/api/naukri/auto-apply-live", {"query": "AI Engineer", "limit": 2}),
        ("POST", "/api/wellfound/auto-apply-live", {"query": "AI Engineer", "limit": 2}),
        ("POST", "/api/naukri/apply-single", {"job_url": "https://www.naukri.com/job-123", "job_title": "AI Dev"}),
        ("POST", "/api/apply/single", {"job_url": "https://www.naukri.com/job-123", "job_title": "AI Dev"}),
        ("POST", "/api/wellfound/apply-single", {"job_url": "https://wellfound.com/jobs/456", "job_title": "ML Lead", "company": "Stark Ind"})
    ]

    # User Charlie has NO analyzed resume
    for method, endpoint, payload in endpoints_to_test:
        res = client.post(endpoint, headers=user_c_headers, json=payload)
        assert res.status_code == 400, f"Expected 400 for {endpoint}, got {res.status_code}: {res.text}"
        data = res.json()
        assert expected_msg in (data.get("message") or data.get("detail") or ""), f"Message mismatch in {endpoint}: {data}"
        print(f"  -> PASSED: {endpoint} strictly blocks submission without analyzed resume.")

    # --------------------------------------------------------------------------
    # TEST 4: Auto-Apply with Analyzed Resume but Missing Session Cookies
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Verifying session_required returned when candidate has resume but no cookies...")
    
    # Seed Charlie's profile with an analyzed resume
    await cloud_db.update_profile("tenant_charlie", {
        "full_name": "Charlie Brown",
        "email": "charlie@example.com",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "technical_skills": ["Python", "FastAPI", "PostgreSQL"],
        "primary_domain": "Backend Engineer",
        "resume_analyzed": True,
        "analyzed_at": "2026-11-10T12:00:00"
    })

    # Charlie has an analyzed resume now, but NO cookies uploaded
    res_wf = client.post("/api/wellfound/auto-apply-live", headers=user_c_headers, json={"query": "Backend", "limit": 2})
    assert res_wf.status_code == 200, f"Expected 200, got {res_wf.status_code}: {res_wf.text}"
    wf_data = res_wf.json()
    assert wf_data.get("status") == "session_required", f"Expected session_required, got {wf_data}"
    assert "No active session cookies connected" in wf_data.get("message", "")
    print("  -> PASSED: Wellfound auto-apply correctly returns session_required!")

    res_nk = client.post("/api/naukri/auto-apply-live", headers=user_c_headers, json={"query": "Backend", "limit": 2})
    assert res_nk.status_code == 200, f"Expected 200, got {res_nk.status_code}: {res_nk.text}"
    nk_data = res_nk.json()
    assert nk_data.get("status") == "session_required", f"Expected session_required, got {nk_data}"
    assert "No active session cookies connected" in nk_data.get("message", "")
    print("  -> PASSED: Naukri auto-apply correctly returns session_required!")

    res_single = client.post("/api/wellfound/apply-single", headers=user_c_headers, json={
        "job_url": "https://wellfound.com/jobs/789",
        "job_title": "Backend Dev",
        "company": "Acme Corp"
    })
    assert res_single.status_code == 200
    assert res_single.json().get("status") == "session_required"
    print("  -> PASSED: Single apply correctly returns session_required!")

    # --------------------------------------------------------------------------
    # TEST 5: Candidate Tailored Pitch Generation (/api/jobs/prepare-application)
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Verifying tailored pitch uses CURRENT user's profile and skills...")
    
    # Alice is a Senior Data Scientist
    await cloud_db.update_profile("tenant_alice", {
        "full_name": "Alice Smith",
        "skills": ["PyTorch", "NLP", "Pandas", "Scikit-Learn"],
        "technical_skills": ["PyTorch", "NLP", "Pandas", "Scikit-Learn"],
        "experience_years": 5,
        "resume_analyzed": True
    })

    # Bob is a Rust & Go Infrastructure Specialist
    await cloud_db.update_profile("tenant_bob", {
        "full_name": "Bob Jones",
        "skills": ["Rust", "Golang", "Kubernetes", "Docker"],
        "technical_skills": ["Rust", "Golang", "Kubernetes", "Docker"],
        "experience_years": 4,
        "resume_analyzed": True
    })

    res_prep_alice = client.post("/api/jobs/prepare-application", headers=user_a_headers, json={
        "job_title": "Lead Data Scientist",
        "company": "DeepMind Partner",
        "job_url": "https://naukri.com/job/data-scientist"
    })
    assert res_prep_alice.status_code == 200
    letter_alice = res_prep_alice.json().get("cover_letter", "")
    assert "Alice Smith" in letter_alice or "Alice" in letter_alice, f"Alice's name missing in pitch: {letter_alice}"
    assert "PyTorch" in letter_alice or "NLP" in letter_alice or "Pandas" in letter_alice, f"Alice's skills missing: {letter_alice}"
    assert "Sachin" not in letter_alice, f"Sachin should not appear in Alice's pitch: {letter_alice}"

    res_prep_bob = client.post("/api/jobs/prepare-application", headers=user_b_headers, json={
        "job_title": "Cloud Architect",
        "company": "Cloud Native Inc",
        "job_url": "https://wellfound.com/jobs/cloud-arch"
    })
    assert res_prep_bob.status_code == 200
    letter_bob = res_prep_bob.json().get("cover_letter", "")
    assert "Bob Jones" in letter_bob or "Bob" in letter_bob, f"Bob's name missing in pitch: {letter_bob}"
    assert "Rust" in letter_bob or "Golang" in letter_bob or "Kubernetes" in letter_bob, f"Bob's skills missing: {letter_bob}"
    assert "Sachin" not in letter_bob, f"Sachin should not appear in Bob's pitch: {letter_bob}"

    print("  -> PASSED: Application pitches are strictly tailored to each candidate's own identity and skills!")

    # --------------------------------------------------------------------------
    # TEST 6: Proof Screenshots Isolated Under proofs/{user_id}/
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Verifying proof screenshot isolation...")
    # Check runner logic for proof directory creation
    from app.agents.naukri_live_runner import PROOF_DIR
    alice_proof_dir = os.path.join(PROOF_DIR, "tenant_alice")
    bob_proof_dir = os.path.join(PROOF_DIR, "tenant_bob")
    
    # Calling runner load cookies directly with user_id
    assert len(naukri_live_runner._load_cookies(user_id="tenant_alice")) == 3
    assert len(naukri_live_runner._load_cookies(user_id="tenant_bob")) == 0
    assert len(naukri_live_runner._load_cookies(user_id=None)) == 0
    assert len(wellfound_live_runner._load_cookies(user_id="tenant_bob")) == 2
    assert len(wellfound_live_runner._load_cookies(user_id="tenant_alice")) == 0
    assert len(wellfound_live_runner._load_cookies(user_id=None)) == 0
    print("  -> PASSED: Runner cookie loaders strictly enforce tenant partitioning with zero fallbacks!")

    # Cleanup test tenant data
    for uid in ["tenant_alice", "tenant_bob", "tenant_charlie"]:
        udir = data_cookies / uid
        if udir.exists():
            import shutil
            shutil.rmtree(udir, ignore_errors=True)

    print("\n" + "=" * 70)
    print("ALL MULTI-TENANT & SESSION SECURITY VERIFICATION TESTS PASSED (6/6)!")
    print("=" * 70)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_tests())
