import base64
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def make_jwt(user_id, email, name):
    def b64url(s):
        return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}))
    payload = b64url(json.dumps({
        "sub": user_id,
        "id": user_id,
        "email": email,
        "user_metadata": {"full_name": name, "name": name},
        "exp": 2000000000
    }))
    sig = b64url("dummy_sig")
    return f"{header}.{payload}.{sig}"

def test_isolation():
    print("[TEST] Running Multi-Tenant Candidate Isolation Test...")
    token_alex = make_jwt("google-alex123", "alex@gmail.com", "Alex Developer")
    token_sarah = make_jwt("github-sarah456", "sarah@github.com", "Sarah Connor")

    # 1. Assert unauthenticated access is blocked (401)
    req_unauth = urllib.request.Request(f"{BASE_URL}/api/memory/qa")
    try:
        urllib.request.urlopen(req_unauth)
        assert False, "Expected 401 for unauthenticated request"
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Expected 401, got {e.code}"
        print("[PASS] 1. Unauthenticated request to /api/memory/qa blocked with 401.")

    # 2. Save memory under Alex
    save_data = json.dumps({
        "question": "What is your specialty?",
        "answer": "Alex is specialized in Distributed Systems."
    }).encode("utf-8")
    req_save = urllib.request.Request(
        f"{BASE_URL}/api/memory/qa",
        data=save_data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token_alex}"}
    )
    res_save = urllib.request.urlopen(req_save)
    assert res_save.status == 200, f"Expected 200, got {res_save.status}"
    print("[PASS] 2. Memory saved for candidate Alex.")

    # 3. Retrieve memories for Alex
    req_alex = urllib.request.Request(
        f"{BASE_URL}/api/memory/qa",
        headers={"Authorization": f"Bearer {token_alex}"}
    )
    res_alex = urllib.request.urlopen(req_alex)
    alex_resp = json.loads(res_alex.read().decode())
    alex_memories = alex_resp.get("memories", [])
    alex_answers = [m.get("answer") for m in alex_memories]
    assert any("Distributed Systems" in a for a in alex_answers), "Alex memory not found in Alex's vault"
    print("[PASS] 3. Alex successfully reads Alex's private memory.")

    # 4. Retrieve memories for Sarah (MUST NOT contain Alex's memory!)
    req_sarah = urllib.request.Request(
        f"{BASE_URL}/api/memory/qa",
        headers={"Authorization": f"Bearer {token_sarah}"}
    )
    res_sarah = urllib.request.urlopen(req_sarah)
    sarah_resp = json.loads(res_sarah.read().decode())
    sarah_memories = sarah_resp.get("memories", [])
    sarah_answers = [m.get("answer") for m in sarah_memories]
    assert not any("Distributed Systems" in a for a in sarah_answers), "LEAK DETECTED: Alex's memory leaked into Sarah's vault!"
    print(f"[PASS] 4. Multi-tenant isolation verified: Sarah's vault contains 0 items from Alex.")

    print("\n=======================================================")
    print("[SUCCESS] MULTI-TENANT ISOLATION FULLY VERIFIED!")
    print("=======================================================")

if __name__ == "__main__":
    test_isolation()
