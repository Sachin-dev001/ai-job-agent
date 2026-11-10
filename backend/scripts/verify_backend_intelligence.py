import os
import sys
import json
import shutil
import asyncio
from pathlib import Path

# Setup path
BACKEND_DIR = Path(r"D:\ai-job-agent\backend")
sys.path.insert(0, str(BACKEND_DIR))

from app.database.supabase_client import cloud_db
from app.agents.naukri_live_runner import naukri_live_runner
from app.agents.wellfound_live_runner import wellfound_live_runner
from app.memory.qa_vault import qa_vault
from app.llm.gemini_service import gemini_service

async def run_tests():
    print("=" * 70)
    print("RUNNING BACKEND INTELLIGENCE & VAULT PERSISTENCE VERIFICATION")
    print("=" * 70)

    test_uid = "test-verification-user"

    # --------------------------------------------------------------------------
    # TEST 1: Cookie Persistence & Auto-Restoration (Survives Ephemeral Restarts)
    # --------------------------------------------------------------------------
    print("\n[TEST 1] Testing Cookie Persistence & Auto-Restoration...")
    dummy_naukri_cookies = [
        {"name": "naukri_test_auth", "value": "auth_token_998877", "domain": ".naukri.com", "path": "/"}
    ]
    dummy_wf_cookies = [
        {"name": "wf_test_auth", "value": "wf_session_445566", "domain": ".wellfound.com", "path": "/"}
    ]

    # Save via cloud_db
    cloud_db.save_cookies_sync(test_uid, "naukri", dummy_naukri_cookies)
    cloud_db.save_cookies_sync(test_uid, "wellfound", dummy_wf_cookies)

    # Verify they were saved in cloud/local profile
    prof = cloud_db.get_profile_sync(test_uid)
    assert prof is not None, "Profile should not be None"
    assert "naukri_cookies" in prof, "naukri_cookies should be in profile"
    assert prof["naukri_cookies"][0]["value"] == "auth_token_998877"
    print("  -> Saved cookies to profile database: OK")

    # Simulate ephemeral disk wipe (e.g. Render redeploy/restart)
    local_cookie_dir = BACKEND_DIR / "data" / "cookies" / str(test_uid)
    if local_cookie_dir.exists():
        shutil.rmtree(local_cookie_dir)
        print("  -> Simulated Render ephemeral container wipe (deleted local disk cache): OK")

    # Now verify naukri_live_runner._load_cookies automatically restores from cloud_db!
    restored_naukri = naukri_live_runner._load_cookies(user_id=test_uid)
    assert len(restored_naukri) > 0, "Should have restored Naukri cookies from cloud database"
    assert restored_naukri[0]["value"] == "auth_token_998877"
    # Verify local disk was auto-repopulated!
    assert (local_cookie_dir / "naukri_cookies.json").exists(), "Should have auto-cached to local disk"
    print(f"  -> Naukri Live Runner auto-restored {len(restored_naukri)} cookies from cloud DB & auto-cached: OK")

    # Verify wellfound_live_runner._load_cookies automatically restores from cloud_db!
    restored_wf = wellfound_live_runner._load_cookies(user_id=test_uid)
    assert len(restored_wf) > 0, "Should have restored Wellfound cookies from cloud database"
    assert restored_wf[0]["value"] == "wf_session_445566"
    assert (local_cookie_dir / "wellfound_cookies.json").exists(), "Should have auto-cached WF to local disk"
    print(f"  -> Wellfound Live Runner auto-restored {len(restored_wf)} cookies from cloud DB & auto-cached: OK")

    # --------------------------------------------------------------------------
    # TEST 2: Tier 1 QA Memory Vault Exact / Semantic Match
    # --------------------------------------------------------------------------
    print("\n[TEST 2] Testing Tier 1 Explicit Candidate Memory Vault...")
    qa_vault.learn("What is your favorite design pattern?", "Repository and Dependency Injection", category="custom", user_id=test_uid)
    tier1_ans = await naukri_live_runner._get_smart_answer("What is your favorite design pattern?", user_id=test_uid)
    assert tier1_ans == "Repository and Dependency Injection", f"Expected exact answer, got {tier1_ans}"
    print(f"  -> Tier 1 Memory Match Answer: '{tier1_ans}': OK")

    # --------------------------------------------------------------------------
    # TEST 3: Tier 2 Candidate Vault Heuristics (Standard Recruiter Screening)
    # --------------------------------------------------------------------------
    print("\n[TEST 3] Testing Tier 2 Candidate Vault & Profile Heuristics...")
    # Update candidate profile with specific values
    await cloud_db.update_profile(test_uid, {
        "current_ctc": "7.2 LPA",
        "expected_ctc": "12 LPA",
        "notice_period": "15 Days",
        "experience_years": 3.5,
        "location": "Bengaluru, India",
        "education": "B.Tech in Artificial Intelligence",
        "skills": ["Python", "FastAPI", "Docker", "PyTorch", "Kubernetes"]
    })

    # Test Notice Period
    ans_notice = await naukri_live_runner._get_smart_answer("What is your notice period?", user_id=test_uid)
    assert "15" in ans_notice, f"Expected 15 in notice, got {ans_notice}"
    print(f"  -> Notice period answer: '{ans_notice}': OK")

    ans_notice_days = await naukri_live_runner._get_smart_answer("How many days notice do you have to serve?", user_id=test_uid)
    assert ans_notice_days == "15", f"Expected numeric '15', got {ans_notice_days}"
    print(f"  -> Notice days answer: '{ans_notice_days}': OK")

    # Test Current CTC
    ans_ctc = await naukri_live_runner._get_smart_answer("What is your current CTC?", user_id=test_uid)
    assert "7.2" in ans_ctc, f"Expected 7.2 in current CTC, got {ans_ctc}"
    print(f"  -> Current CTC answer: '{ans_ctc}': OK")

    ans_ctc_lpa = await naukri_live_runner._get_smart_answer("Current salary in LPA?", user_id=test_uid)
    assert ans_ctc_lpa == "7.2", f"Expected '7.2', got {ans_ctc_lpa}"
    print(f"  -> Current CTC in LPA: '{ans_ctc_lpa}': OK")

    # Test Expected CTC
    ans_exp_ctc = await naukri_live_runner._get_smart_answer("Expected salary in LPA?", user_id=test_uid)
    assert ans_exp_ctc == "12", f"Expected '12', got {ans_exp_ctc}"
    print(f"  -> Expected CTC in LPA: '{ans_exp_ctc}': OK")

    # Test Total Experience
    ans_exp = await naukri_live_runner._get_smart_answer("Total work experience in years?", user_id=test_uid)
    assert ans_exp == "3.5", f"Expected '3.5', got {ans_exp}"
    print(f"  -> Total experience: '{ans_exp}': OK")

    # Test Specific Skill Experience
    ans_skill_num = await naukri_live_runner._get_smart_answer("How many years of experience in Python?", user_id=test_uid)
    assert ans_skill_num == "3.5", f"Expected '3.5', got {ans_skill_num}"
    print(f"  -> Specific skill experience in years: '{ans_skill_num}': OK")

    ans_skill_yn = await naukri_live_runner._get_smart_answer("Do you have hands-on experience in Kubernetes?", user_id=test_uid)
    assert ans_skill_yn == "Yes", f"Expected 'Yes', got {ans_skill_yn}"
    print(f"  -> Specific skill Yes/No match: '{ans_skill_yn}': OK")

    # Test Relocation and Location
    ans_reloc = await naukri_live_runner._get_smart_answer("Are you willing to relocate for this role?", user_id=test_uid)
    assert ans_reloc == "Yes", f"Expected 'Yes', got {ans_reloc}"
    print(f"  -> Relocation answer: '{ans_reloc}': OK")

    ans_loc = await naukri_live_runner._get_smart_answer("Where are you currently located?", user_id=test_uid)
    assert "Bengaluru" in ans_loc, f"Expected Bengaluru in location, got {ans_loc}"
    print(f"  -> Current location answer: '{ans_loc}': OK")

    # Test Qualification
    ans_qual = await naukri_live_runner._get_smart_answer("What is your highest degree?", user_id=test_uid)
    assert "B.Tech" in ans_qual, f"Expected B.Tech, got {ans_qual}"
    print(f"  -> Qualification answer: '{ans_qual}': OK")

    # --------------------------------------------------------------------------
    # TEST 4: Tier 3 LLM Auto-Answer Grounded in Candidate Facts
    # --------------------------------------------------------------------------
    print("\n[TEST 4] Testing Tier 3 LLM Auto-Answer...")
    open_q = "Briefly describe your experience designing asynchronous REST APIs with FastAPI."
    tier3_ans = await naukri_live_runner._get_smart_answer(open_q, job_title="Senior Backend Engineer", company="Stripe", user_id=test_uid)
    assert tier3_ans and len(tier3_ans) > 10, f"Expected substantive LLM auto-answer, got: {tier3_ans}"
    print(f"  -> LLM Auto-Answer for '{open_q}':\n     \"{tier3_ans}\": OK")

    # --------------------------------------------------------------------------
    # TEST 5: Option Selection Heuristics & Intelligence
    # --------------------------------------------------------------------------
    print("\n[TEST 5] Testing Option Selection Intelligence...")
    opts1 = ["90 Days", "60 Days", "30 Days", "15 Days or less"]
    idx1 = await naukri_live_runner._get_best_option_index("Notice period", opts1, user_id=test_uid)
    assert idx1 == 3, f"Expected option index 3 ('15 Days or less'), got {idx1}"
    print(f"  -> Notice option picked: [{idx1}] '{opts1[idx1]}': OK")

    opts2 = ["No", "Not sure", "Yes, definitely"]
    idx2 = await naukri_live_runner._get_best_option_index("Are you comfortable working in Bengaluru?", opts2, user_id=test_uid)
    assert idx2 == 2, f"Expected option index 2 ('Yes, definitely'), got {idx2}"
    print(f"  -> Yes/No option picked: [{idx2}] '{opts2[idx2]}': OK")

    # --------------------------------------------------------------------------
    # TEST 6: Main.py Endpoints and Defaults
    # --------------------------------------------------------------------------
    print("\n[TEST 6] Testing Main.py Request Schemas & Endpoints...")
    from main import SingleJobApplyRequest
    req = SingleJobApplyRequest(job_url="https://www.naukri.com/job-listings-123", job_title="AI Engineer", company="Google")
    assert req.company == "Google", "SingleJobApplyRequest should accept company"
    print("  -> SingleJobApplyRequest company attribute: OK")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_tests())
