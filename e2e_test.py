import os
import requests
import json
import time

BASE_URL = os.getenv("VIGIL_BASE_URL", "http://localhost:8000/api/v1")
STAFF_ID = os.getenv("VIGIL_E2E_STAFF_ID", "NURSE_101")
PASSWORD = os.getenv("VIGIL_E2E_PASSWORD") or os.getenv("VIGIL_SEED_DEMO_PASSWORD", "")

def run_e2e_test():
    if not PASSWORD:
        raise SystemExit("Set VIGIL_E2E_PASSWORD or VIGIL_SEED_DEMO_PASSWORD before running the e2e test")

    print("Starting e2e test against Postgres backend...")
    
    # 1. Login to get token
    login_data = {"staff_id": STAFF_ID, "password": PASSWORD}
    resp = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if resp.status_code != 200:
        print("Login failed!", resp.text)
        return
    token = resp.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Ingest an event with a raw note
    event = {
        "client_sync_id": f"sync-e2e-{int(time.time())}",
        "event_type": "nursing_round",
        "patient_id": "PAT_1001",
        "ward_id": "ICU_01",
        "staff_id": STAFF_ID,
        "device_timestamp": "2023-01-01T10:00:00Z", # Very old, will trigger overdue gap immediately
        "payload": {},
        "raw_note": "Patient refused blood pressure check, said they wanted to sleep."
    }
    print("\nIngesting event with free text note (should trigger CaptureAgent)...")
    resp = requests.post(f"{BASE_URL}/events/ingest", json={"events": [event]}, headers=headers)
    print("Ingest Status:", resp.status_code, resp.json())
    
    # 3. Trigger Gap Detection
    print("\nTriggering Gap Detection Pipeline (Expectation -> GapDetection -> Notifications)...")
    resp = requests.post(f"{BASE_URL}/gaps/trigger", headers=headers)
    print("Trigger Status:", resp.status_code, resp.json())
    
    # 4. Fetch Gaps
    print("\nFetching detected gaps...")
    resp = requests.get(f"{BASE_URL}/gaps", headers=headers)
    print("Gaps:", json.dumps(resp.json(), indent=2))
    
    # 5. Trigger Evidence Generation
    print("\nTriggering Evidence/CAPA Generation...")
    resp = requests.post(f"{BASE_URL}/evidence/generate", headers=headers)
    print("Evidence Trigger Status:", resp.status_code, resp.json())
    
    # 6. Fetch Evidence
    print("\nFetching generated evidence/CAPAs...")
    resp = requests.get(f"{BASE_URL}/evidence", headers=headers)
    print("Evidence:", json.dumps(resp.json(), indent=2))
    print("\nE2E Test Complete.")

if __name__ == "__main__":
    run_e2e_test()
