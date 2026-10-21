# Vigil — Clinical Event Verification Prototype

> 📖 **Looking to run this locally?** See the comprehensive [SETUP.md](file:///Users/akshitkapoor/Documents/Health%20Care/SETUP.md) for full Docker Compose & native setup instructions, workflow walk-throughs, and demo scenarios.

**Vigil** is an on-premise continuous verification system for hospitals. It verifies that time-bound clinical actions (nursing rounds, informed consent capture, medication order documentation) actually happen on schedule, flags gaps in real time, and generates audit-evidence records for hospitals seeking or maintaining **NABH accreditation**.

---

## Architecture & Principles

1. **On-Prem Default:** Runs entirely inside the hospital's local network (LAN).
2. **Append-Only Event Store:** Historical clinical actions are never mutated or overwritten. Current state is computed on demand via SQL derived views.
3. **Deterministic Core Logic:** Clinical rules and schedules are deterministic code driven by config; LLMs structure language without deciding clinical thresholds.
4. **Configuration-Driven:** Ward lists, staff roles, and protocol cadences are managed in `backend/config/hospital_settings.yaml`.

---

## Phase 1 Deliverables & Features

- **Mobile/Tablet PWA Capture App (`mobile-app/`):**
  - Built as an offline-first Progressive Web App (PWA) with Workbox Service Worker app-shell caching. Operates fully in airplane mode / zero Wi-Fi ward environments.
  - IndexedDB local event queue (`services/local_db.js`) supporting offline queuing, status tracking (`pending`, `synced`, `failed`), and error inspection.
  - Structured forms for:
    - **Nursing Round Verification:** Vitals (BP, Pulse, SpO2, Temp, Pain score), position changes, IV site inspection, raw notes.
    - **Informed Consent Capture:** Procedure name, attending doctor, NABH risk checklist, HTML5 canvas digital signature capture, witness details.
    - **Medication Order Documentation:** Drug name, dosage, route, high-alert flag, and dual-nurse verification.
- **REST Ingestion API & Backend (`backend/`):**
  - **FastAPI** backend with role-based JWT access control (RBAC).
  - **Per-Event Batch Ingestion (`POST /api/v1/events/ingest`):** Itemized processing where individual event failures return error details without blocking valid batch items.
  - **Idempotency:** Unique `client_sync_id` prevents duplicate inserts upon network re-sync.
  - **Reference Tables & Integrity:** `staff`, `patients`, and `wards` tables validate foreign keys during event ingestion.
  - **Lightweight Signature Storage:** Digital canvas signatures are saved as image file blobs (`backend/uploads/signatures/`), keeping JSONB payloads lightweight.
  - **Timezone Preservation:** Preserves `device_timestamp` with offset (`+05:30`) alongside server `ingested_at` UTC timestamp.
  - **Derived SQL Views:** `v_latest_nursing_rounds`, `v_patient_consents`, `v_medication_order_docs`.

---

## Quickstart — How to Run Locally

### 1. Run Backend API Server

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start backend server
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000
```

Open interactive Swagger documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Run Automated Test Suite

```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/test_backend.py -v
```

### 3. Run Mobile/Tablet Capture App (PWA)

```bash
cd mobile-app
npm install
npm run dev
```

Open tablet capture app in browser at [http://localhost:3000](http://localhost:3000).

Demo Login Credentials:
- **Staff ID:** `NURSE_101`
- **Password:** `NursePassword123!`

---

## Docker Deployment (Hospital On-Prem Hardware)

Run the full stack with single command:

```bash
docker-compose up --build
```

- **Backend API & Swagger Docs:** `http://localhost:8000` / `http://localhost:8000/docs`
- **Mobile Tablet Capture App (Docker):** `http://localhost:3001` (or `http://localhost:3000` when running via `npm run dev`)
- **Postgres Event Store:** `localhost:5432`

---

## Phase 1 Verification Checklist

- [x] **PWA Airplane Mode:** Toggle Airplane mode / Offline in browser DevTools. App shell loads completely offline. Logging a round, consent form, or med order queues events in IndexedDB.
- [x] **Batch Sync & Itemized Errors:** Reconnecting network and triggering sync posts batch to `/api/v1/events/ingest`. If 1 event has an invalid patient ID, valid events succeed and the invalid event is marked as `failed` with error reason.
- [x] **Idempotency:** Re-triggering sync returns `status: "duplicate"` without double-inserting records.
- [x] **Derived Views:** Fetching `/api/v1/events/views/latest-rounds` returns latest patient vitals calculated dynamically from append-only events.
- [x] **Phase 1 Stubs:** `/api/v1/gaps` and `/api/v1/evidence` return `501 Not Implemented`.

---

## Note on Assumptions & Spec Alignment

1. **Staff & Patient Integrity:** Implemented `staff`, `patients`, and `wards` relational tables in Postgres. `hospital_settings.yaml` seeds default wards and admin credentials upon startup.
2. **PWA App Shell:** Utilized Vite + React + Workbox Service Worker (`vite-plugin-pwa`) to satisfy the requirement for airplane-mode readiness in Wi-Fi blindspots in hospital wards.
3. **Blob Signature Storage:** Signature drawings are saved to disk (`/backend/uploads/signatures/`) with signature reference links stored in payload JSONB.
