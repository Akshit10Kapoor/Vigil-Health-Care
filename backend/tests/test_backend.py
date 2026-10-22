from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["system"] == "Vigil Clinical Event Verification"
    assert data["phase"] == 1

def test_auth_login_success():
    response = client.post(
        "/api/v1/auth/login",
        json={"staff_id": "NURSE_101", "password": "TestNursePassword123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "nurse"
    assert data["staff_id"] == "NURSE_101"

def test_auth_login_invalid():
    response = client.post(
        "/api/v1/auth/login",
        json={"staff_id": "NURSE_101", "password": "WrongPassword"}
    )
    assert response.status_code == 401

def test_get_wards_and_patients():
    wards_res = client.get("/api/v1/wards")
    assert wards_res.status_code == 200
    wards = wards_res.json()
    assert len(wards) >= 1
    assert any(w["ward_id"] == "ICU_01" for w in wards)

    patients_res = client.get("/api/v1/patients?ward_id=ICU_01")
    assert patients_res.status_code == 200
    patients = patients_res.json()
    assert len(patients) >= 1
    assert any(p["patient_id"] == "PAT_1001" for p in patients)

def test_batch_event_ingestion_and_idempotency():
    # 1. Ingest batch containing 2 valid events (Round + Consent) and 1 invalid patient event
    payload = {
        "events": [
            {
                "client_sync_id": "sync_test_001",
                "event_type": "nursing_round",
                "patient_id": "PAT_1001",
                "ward_id": "ICU_01",
                "bed_number": "Bed-01",
                "staff_id": "NURSE_101",
                "device_timestamp": "2026-07-30T15:30:00+05:30",
                "device_tz_offset": "+05:30",
                "payload": {
                    "vitals": {"bp": "120/80", "spo2": 98, "pulse": 72},
                    "position_change": "Left lateral",
                    "iv_site_check": "Clean, no swelling"
                },
                "raw_note": "Patient calm, vitals stable"
            },
            {
                "client_sync_id": "sync_test_002",
                "event_type": "consent_capture",
                "patient_id": "PAT_1001",
                "ward_id": "ICU_01",
                "staff_id": "NURSE_101",
                "device_timestamp": "2026-07-30T15:35:00+05:30",
                "device_tz_offset": "+05:30",
                "payload": {
                    "procedure_name": "Central Line Insertion",
                    "doctor_name": "Dr. Aris Thorne",
                    "risks_explained": True,
                    "signature_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                }
            },
            {
                "client_sync_id": "sync_test_003_bad",
                "event_type": "nursing_round",
                "patient_id": "NON_EXISTENT_PATIENT",
                "ward_id": "ICU_01",
                "staff_id": "NURSE_101",
                "device_timestamp": "2026-07-30T15:40:00+05:30",
                "payload": {}
            }
        ]
    }

    res = client.post("/api/v1/events/ingest", json=payload)
    assert res.status_code == 200
    data = res.json()
    print("INGEST DATA DEBUG:", data)
    assert data["total"] == 3
    assert data["success_count"] == 2

    assert data["failed_count"] == 1

    results_by_sync = {r["client_sync_id"]: r for r in data["results"]}
    assert results_by_sync["sync_test_001"]["status"] == "success"
    assert results_by_sync["sync_test_002"]["status"] == "success"
    assert results_by_sync["sync_test_003_bad"]["status"] == "error"

    # 2. Test Idempotency (resending batch returns 'duplicate' for existing events)
    res_retry = client.post("/api/v1/events/ingest", json=payload)
    assert res_retry.status_code == 200
    retry_data = res_retry.json()
    retry_by_sync = {r["client_sync_id"]: r for r in retry_data["results"]}
    assert retry_by_sync["sync_test_001"]["status"] == "duplicate"
    assert retry_by_sync["sync_test_002"]["status"] == "duplicate"

def test_derived_latest_rounds_view():
    ingest_res = client.post("/api/v1/events/ingest", json={
        "events": [{
            "client_sync_id": "sync_view_001",
            "event_type": "nursing_round",
            "patient_id": "PAT_1001",
            "ward_id": "ICU_01",
            "bed_number": "Bed-01",
            "staff_id": "NURSE_101",
            "device_timestamp": "2026-07-30T16:30:00+05:30",
            "payload": {
                "vitals": {"bp": "118/76", "spo2": 98, "pulse": 74},
                "position_change": "Supine",
                "iv_site_check": "Clean"
            }
        }]
    })
    assert ingest_res.status_code == 200, ingest_res.text
    assert ingest_res.json()["success_count"] == 1

    res = client.get("/api/v1/events/views/latest-rounds?ward_id=ICU_01")
    assert res.status_code == 200
    rounds = res.json()
    assert len(rounds) >= 1
    patient_round = next((r for r in rounds if r["patient_id"] == "PAT_1001"), None)
    assert patient_round is not None
    assert patient_round["payload"]["vitals"]["spo2"] == 98

def test_gap_and_evidence_endpoints(nurse_headers):
    gaps_res = client.get("/api/v1/gaps/", headers=nurse_headers)
    assert gaps_res.status_code == 200
    assert isinstance(gaps_res.json(), list)

    evidence_res = client.get("/api/v1/evidence/", headers=nurse_headers)
    assert evidence_res.status_code == 200
    assert isinstance(evidence_res.json(), list)


def test_gap_and_evidence_endpoints_require_auth():
    assert client.get("/api/v1/gaps/").status_code == 401
    assert client.get("/api/v1/evidence/").status_code == 401
