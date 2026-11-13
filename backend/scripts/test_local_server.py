import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx
import uvicorn
import multiprocessing
import time
from local_agent.server import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="warning")

async def test_endpoints():
    print("[TEST] Testing Local Web Dashboard endpoints on port 8899...")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8899", timeout=10.0) as client:
        # 1. UI Root
        r1 = await client.get("/")
        print(f"[TEST] GET / -> Status {r1.status_code}, Length: {len(r1.text)}")
        assert r1.status_code == 200
        assert "AutoApply Local Agent" in r1.text

        # 2. Status API
        r2 = await client.get("/api/status")
        print(f"[TEST] GET /api/status -> Status {r2.status_code}, Body: {r2.json()}")
        assert r2.status_code == 200
        assert "naukri_connected" in r2.json()

        # 3. Profile API
        r3 = await client.get("/api/profile")
        print(f"[TEST] GET /api/profile -> Status {r3.status_code}, Candidate: {r3.json().get('full_name')}")
        assert r3.status_code == 200

        # 4. Proofs API
        r4 = await client.get("/api/proofs")
        print(f"[TEST] GET /api/proofs -> Status {r4.status_code}, Proofs Count: {len(r4.json().get('proofs', []))}")
        assert r4.status_code == 200

    print("\n==========================================")
    print("🎉 LOCAL WEB DASHBOARD TESTS PASSED 100%!")
    print("==========================================")

if __name__ == "__main__":
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()
    time.sleep(2.0)
    try:
        asyncio.run(test_endpoints())
    finally:
        proc.terminate()
