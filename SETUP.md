# Vigil — Local Setup & Operations Guide

This guide provides complete instructions to set up, operate, and troubleshoot the **Vigil Clinical Event Verification System** locally.

The entire stack is containerized with **Docker Compose**, allowing you to spin up the database, API server, and mobile tablet PWA with a single command. Instructions for native (bare-metal) development are also included.

---

## Table of Contents

1. [System Architecture & Container Topology](#system-architecture--container-topology)
2. [Prerequisites](#prerequisites)
3. [Quickstart: Running with Docker Compose](#quickstart-running-with-docker-compose)
4. [Service Endpoints & Access URLs](#service-endpoints--access-urls)
5. [Seeded Credentials (Local Development Only)](#seeded-credentials-local-development-only)
6. [Populating Demo Data & Scenarios](#populating-demo-data--scenarios)
7. [Operating the Application (Core Workflows)](#operating-the-application-core-workflows)
   - [1. Ward Dashboard & Monitoring](#1-ward-dashboard--monitoring)
   - [2. Nursing Rounds & Vitals Logging](#2-nursing-rounds--vitals-logging)
   - [3. Informed Consent Capture & Digital Signature](#3-informed-consent-capture--digital-signature)
   - [4. High-Alert Medication Order Verification](#4-high-alert-medication-order-verification)
   - [5. Offline-First PWA Mode (Airplane / Zero Wi-Fi)](#5-offline-first-pwa-mode-airplane--zero-wi-fi)
   - [6. Gap History & Real-Time Protocol Alerts](#6-gap-history--real-time-protocol-alerts)
   - [7. NABH Evidence & CAPA Pack Export](#7-nabh-evidence--capa-pack-export)
8. [Automated Verification & Tests](#automated-verification--tests)
9. [Alternative: Native Local Development (Without Docker)](#alternative-native-local-development-without-docker)
10. [Configuration & Customization](#configuration--customization)
11. [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## System Architecture & Container Topology

Vigil is composed of three interconnected services defined in [docker-compose.yml](file:///Users/akshitkapoor/Documents/Health%20Care/docker-compose.yml):

```
                      ┌───────────────────────────────────────────────┐
                      │              Hospital Network (LAN)           │
                      │                                               │
                      │   Nurse Tablet / Browser (PWA)                │
                      │   http://localhost:3001                       │
                      └───────────────────────┬───────────────────────┘
                                              │ HTTP / JSON Batch
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Docker Compose Network                                                          │
│                                                                                 │
│   ┌────────────────────────────────┐         ┌──────────────────────────────┐   │
│   │ container: vigil_mobile_app    │         │ container: vigil_backend     │   │
│   │ (node:20-alpine / serve)       │         │ (python:3.11 / FastAPI)      │   │
│   │ Host Port: 3001 -> Cont: 3000  │         │ Port: 8000:8000              │   │
│   └────────────────────────────────┘         └──────────────┬───────────────┘   │
│                                                             │                   │
│                                                             │ SQLAlchemy        │
│                                                             ▼                   │
│                                              ┌──────────────────────────────┐   │
│                                              │ container: vigil_postgres    │   │
│                                              │ (postgres:16-alpine)         │   │
│                                              │ Internal network only        │   │
│                                              │ Volume: postgres_data        │   │
│                                              └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

| Service | Container Name | Port Mapping | Description |
| :--- | :--- | :--- | :--- |
| **Database** | `vigil_postgres` | Internal only | PostgreSQL 16 store with an append-only, hash-chained clinical event schema, FK constraints, append-only triggers, and derived SQL views. Initialized via `backend/event_store/schema/init_db.sql`; `zz_create_app_role.sh` provisions the least-privilege `vigil_app` role. Not published to the host by default. |
| **Backend API** | `vigil_backend` | `8000:8000` | FastAPI application providing authentication, batch ingestion, LangGraph multi-agent pipeline (Expectation, GapDetection, Evidence), and static signature blob storage. |
| **Mobile App (PWA)** | `vigil_mobile_app` | `3001:3000` | Offline-first Progressive Web App built with React, Vite, TailwindCSS, and Workbox Service Worker. Stores offline events in client-side IndexedDB. |

---

## Prerequisites

Before starting, ensure you have installed:

- **Docker Desktop** (Engine 20.10+ / Compose v2.0+): [Download Docker](https://www.docker.com/products/docker-desktop/)
- Ensure the Docker daemon is running on your machine (open the Docker Desktop app).

*(Optional for native bare-metal development only)*:
- **Python 3.11+**
- **Node.js 20+** and **npm**

---

## Quickstart: Running with Docker Compose

### 1. Start the Docker Daemon
Launch the **Docker Desktop** application on your machine and confirm it is running.

### 2. Configure Secrets
Vigil has no default credentials. Copy the example environment file and fill in strong, unique values:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set at least `POSTGRES_PASSWORD`, `VIGIL_APP_DB_PASSWORD`, and `SECRET_KEY`. To bootstrap the first admin account, set `VIGIL_SEED_ADMIN_PASSWORD` and `VIGIL_AUTO_SEED=true` for the first startup, then set `VIGIL_AUTO_SEED=false` again.

The API connects as the least-privilege `vigil_app` role. It can append clinical events but cannot `UPDATE`, `DELETE`, or `TRUNCATE` them. Use a URL-safe password (for example from `secrets.token_urlsafe`).

### 3. Launch the Application Stack
From the project root directory, run:

```bash
docker compose up --build
```

> **Tip:** To run containers in detached (background) mode, append `-d`:
> ```bash
> docker compose up --build -d
> ```

Docker Compose will automatically:
1. Start PostgreSQL and wait for its healthcheck (`pg_isready`) to pass.
2. Execute the initial SQL schema (`init_db.sql`) and provision the `vigil_app` role (`zz_create_app_role.sh`).
3. Build and launch the FastAPI backend as `vigil_app`. Seeding is opt-in via `VIGIL_AUTO_SEED`; demo staff/patients require additional explicit flags. The backend refuses to start unless the integrity schema and append-only triggers are present, and it verifies the full hash chain at startup. If a later scheduled verification fails, clinical event ingestion is halted until a verification succeeds.
4. Build the PWA production assets and serve them via Node.

### 4. Check Container Status
Verify that all 3 containers are healthy and running:

```bash
docker compose ps
```

You should see:
- `vigil_postgres` (Up, healthy)
- `vigil_backend` (Up)
- `vigil_mobile_app` (Up)

### 5. View Container Logs
To follow live logs from all services:

```bash
docker compose logs -f
```

Or inspect a specific container (e.g. backend):
```bash
docker compose logs -f backend
```

### 6. Stop the Application
To stop all services:

```bash
docker compose down
```

To stop and completely purge the database volume (clean reset):
```bash
docker compose down -v
```

---

## Service Endpoints & Access URLs

Once running, access the services using these URLs:

| Service | URL | Purpose |
| :--- | :--- | :--- |
| **Tablet Capture PWA** | [http://localhost:3001](http://localhost:3001) | Nurse & Admin clinical portal (rounds, consent, meds, gaps, evidence) |
| **Backend API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI for testing API routes |
| **API Healthcheck** | [http://localhost:8000/](http://localhost:8000/) | System status JSON response |
| **PostgreSQL DB** | Internal Docker network only | Use `docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"` from the project root. For native development, see the loopback-only override below. |

---

## Seeded Credentials (Local Development Only)

Vigil no longer ships default passwords. Staff records are seeded only when you opt in via environment variables:

- `VIGIL_SEED_ADMIN_PASSWORD` bootstraps `ADMIN_01`.
- `VIGIL_SEED_DEMO_USERS=true` plus `VIGIL_SEED_DEMO_PASSWORD` bootstraps the demo nurses.
- `VIGIL_SEED_DEMO_PATIENTS=true` adds sample patients.

Staff IDs and ward assignments live in [hospital_settings.yaml](file:///Users/akshitkapoor/Documents/Health%20Care/backend/config/hospital_settings.yaml); passwords come only from environment variables.

| Role | Staff ID | Password | Assigned Ward | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **ICU Duty Nurse** | `NURSE_101` | value of `VIGIL_SEED_DEMO_PASSWORD` | Intensive Care Unit (`ICU_01`) | Log rounds, record vitals, capture consent, administer high-alert meds |
| **Surgical Nurse** | `NURSE_102` | value of `VIGIL_SEED_DEMO_PASSWORD` | Surgical Ward 3A (`SURG_3A`) | Surgical rounds, pre-op checklist, consent capture |
| **ICU Secondary Nurse** | `NURSE_103` | value of `VIGIL_SEED_DEMO_PASSWORD` | Intensive Care Unit (`ICU_01`) | Co-signing high-alert medication dual verification |
| **Hospital Quality Admin** | `ADMIN_01` | value of `VIGIL_SEED_ADMIN_PASSWORD` | *All Wards* | Access gap analysis, trigger verification pipelines, export NABH evidence |

Never enable the demo flags in a real hospital deployment.

---

## Populating Demo Data & Scenarios

To populate realistic clinical records and simulated compliance gaps (e.g., overdue ICU vitals, missing surgical consent):

### Running the Seed Script via Docker:
The script drops and recreates the schema, so it requires an explicit opt-in and a demo password:
```bash
docker compose exec -e VIGIL_ALLOW_DEMO_RESET=1 backend python backend/scripts/seed_comprehensive_demo.py
```
It reads `VIGIL_SEED_DEMO_PASSWORD` (and optionally `VIGIL_SEED_ADMIN_PASSWORD`) from the backend environment.

### What this script configures:
- Cleans and re-initializes database schema.
- Configures 3 wards: `ICU_01` (High acuity), `SURG_3A` (Medium acuity), `GEN_01` (Low acuity).
- Populates 5 diverse patients:
  - `PAT_001` (Arjun Mehta - ICU Bed 1): Missed vitals (>2 hours overdue) triggering an **Urgent Gap Alert**.
  - `PAT_002` (Sunita Rao - ICU Bed 2): Complete up-to-date vitals logged.
  - `PAT_003` (Vikram Singh - SURG Bed 12): Central line insertion consent signed with valid digital signature.
  - `PAT_004` (Priya Patel - SURG Bed 14): Emergency Laparotomy scheduled with missing consent, triggering an **Overdue Consent Gap**.
  - `PAT_005` (Ramesh Verma - GEN Bed 4): General ward patient on 8-hour round interval.
- Automatically invokes the **LangGraph multi-agent verification pipeline** (`ExpectationAgent` $\to$ `GapDetectionAgent` $\to$ `EvidenceAgent`).

---

## Operating the Application (Core Workflows)

### 1. Ward Dashboard & Monitoring
1. Open [http://localhost:3001](http://localhost:3001) in Chrome, Edge, or Safari.
2. Sign in as `ADMIN_01` using the password you set in `VIGIL_SEED_ADMIN_PASSWORD`.
3. View the **Overview**:
   - Total patients admitted across wards.
   - Active Urgent & Warning clinical flags.
   - Real-time round compliance breakdown.
   - Quick navigation shortcuts via keyboard (`Cmd+K` or `Ctrl+K` opens the Command Palette).

### 2. Nursing Rounds & Vitals Logging
1. Sign in as `NURSE_101` using the password you set in `VIGIL_SEED_DEMO_PASSWORD`.
2. Navigate to **Nursing Rounds** in the sidebar.
3. Select a patient (e.g. `PAT_1001 - Ramesh Verma`).
4. Enter clinical readings:
   - **Vitals:** Blood Pressure (e.g., `120/80`), Pulse (`78 bpm`), SpO2 (`98%`), Temperature (`98.6 °F`), Pain Score (`0-10`).
   - **Patient Position:** Supine, Left lateral, Right lateral, Fowler's, or Prone.
   - **IV Site Inspection:** Confirm insertion site is clean with no erythema/phlebitis.
   - **Free-text Note:** Type clinical notes (e.g., *"Patient resting comfortably after nebulization"*). The backend `CaptureAgent` automatically extracts unstructured vitals from free text.
5. Click **Submit Round Verification**.

### 3. Informed Consent Capture & Digital Signature
1. In the sidebar, select **Informed Consent**.
2. Select patient and specify:
   - Procedure name (e.g. *Central Venous Line Placement*).
   - Attending doctor name.
   - Check the **NABH Risk Checklist** items (Risks explained, alternatives discussed, patient answered questions).
3. Have the patient or legal guardian draw their signature on the interactive **HTML5 canvas touch pad**.
4. Enter witness staff details.
5. Click **Lock & Save Informed Consent**. The signature is saved as an immutable image blob in `backend/uploads/signatures/` with its hash and metadata preserved in PostgreSQL.

### 4. High-Alert Medication Order Verification
1. Navigate to **Medication Orders**.
2. Input the medication name (e.g., *Potassium Chloride 20 mEq IV* or *Heparin*).
3. Toggle the **High-Alert Drug** switch.
4. Notice that high-alert drugs enforce **dual-nurse verification** per NABH standards.
5. Enter the second verifying nurse's ID (`NURSE_103`) to authenticate the co-signature.
6. Click **Log Administration**.

### 5. Offline-First PWA Mode (Airplane / Zero Wi-Fi)
Vigil is designed for hospital Wi-Fi dead-zones:
1. Open DevTools in your browser (`F12` or `Cmd+Option+I`).
2. Go to the **Network** tab and change throttling from *No throttling* to **Offline**.
3. Notice the top status bar switches to **Offline Mode (Queued locally)**.
4. Perform nursing rounds or log medication. The app saves the records immediately to local **IndexedDB** (`vigil_pwa_db`).
5. Open the **Sync Status** screen to inspect pending un-synced items.
6. Re-enable network in DevTools (switch back to **Online**).
7. Click **Sync All** or let the automatic reconnect handler push pending events to `POST /api/v1/events/ingest`.
8. The backend ensures **idempotent ingestion** using `client_sync_id`, preventing duplicate entries even if sync is triggered repeatedly.

### 6. Gap History & Real-Time Protocol Alerts
1. Click **Gap History** in the navigation.
2. Inspect detected protocol violations:
   - **Urgent:** Overdue ICU round (>120 mins elapsed without logged vitals).
   - **Warning:** Overdue Surgical ward round (>240 mins).
   - **Consent Missing:** Procedure scheduled without executed consent.
3. You can click **Trigger Verification Pipeline** to manually run the LangGraph agent workflow on demand.

### 7. NABH Evidence & CAPA Pack Export
1. Navigate to **Evidence Export**.
2. View generated corrective action recommendations structured according to the **NABH 6th Edition Chapters** (effective 1 January 2025):
   - **Chapter COP (Care of Patients):** Round compliance and escalation records.
   - **Chapter AAC (Access, Assessment, and Continuity):** Consent verification.
   - **Chapter MOM (Management of Medication):** High-alert dual-nurse co-signing logs.
3. Click **Download NABH Evidence PDF** to generate an audit-ready compliance document directly in your browser.

---

## Automated Verification & Tests

### 1. Run End-to-End Test Script
While the Docker stack is running, execute the automated verification test:

```bash
python e2e_test.py
```

This script:
- Logs in as `NURSE_101` and retrieves a JWT access token.
- Ingests a new clinical round event with free-text note.
- Triggers the background LangGraph gap detection pipeline.
- Asserts detected clinical gaps.
- Triggers evidence and CAPA draft generation.

### 2. Generate CLI Text Evidence Report
To generate a formatted audit report to `evidence-export/latest_report.txt`:

```bash
python evidence-export/generator.py
```

### 3. Run Backend Pytest Suite
To run backend unit and integration tests:

```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/ -v
```

By default the suite uses SQLite. To run the same tests against PostgreSQL (recommended before release), point `TEST_DATABASE_URL` at a disposable database whose name contains `test`:

```bash
createdb -h 127.0.0.1 -U postgres vigil_integrity_test
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/vigil_integrity_test \
PYTHONPATH=. ./venv/bin/pytest backend/tests/ -v
```

On PowerShell:

```powershell
$env:TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:5432/vigil_integrity_test'
python -m pytest backend/tests/ -q
```

The test harness refuses to reset a database unless its name contains `test`. The PostgreSQL run exercises concurrent appends, append-only enforcement, correction events, and app-role grants; SQLite skips only those PostgreSQL-specific tests.

### 4. Verify the Hash Chain

Run the verifier against the configured database:

```bash
python -m backend.scripts.verify_integrity
python -m backend.scripts.verify_integrity --record   # append result to chain_verification_logs
```

It exits non-zero and reports the first invalid event position if the chain, links, or persisted head do not match. The API runs the same verification at startup; a failed periodic check halts new clinical event ingestion until a later check passes. Admin/quality users can also call:

- `GET /api/v1/integrity/chain` - current head, state, and trigger status.
- `POST /api/v1/integrity/chain/verify` - full verification, optionally recorded.

### 5. Migrate an Existing Database

Existing databases must be migrated before running the integrity-enabled backend. Docker init scripts run only on a fresh volume; a pre-existing `postgres_data` volume needs this migration. The migration backfills hashes in place, refuses to proceed if an existing hashed prefix is invalid, installs triggers, and is safe to re-run:

```bash
MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/vigil_db \
python -m backend.scripts.migrate_integrity
python -m backend.scripts.migrate_integrity --check
```

To create/update the least-privilege application role as part of the migration:

```bash
MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/vigil_db \
VIGIL_APP_DB_PASSWORD='<url-safe-password>' \
python -m backend.scripts.migrate_integrity --create-app-role
```

Then point the backend's `DATABASE_URL` at `vigil_app`. Do not run `init_db.sql` against an existing populated database; it intentionally refuses to seed genesis over existing events.

---

## Alternative: Native Local Development (Without Docker)

If you prefer to run services natively without Docker containers:

### 1. Start Local PostgreSQL
Ensure PostgreSQL is running locally on port 5432 with a database named `vigil_db`:
```bash
createdb vigil_db
psql -d vigil_db -f backend/event_store/schema/init_db.sql
# Fresh database only; for an existing populated database use migrate_integrity.py
```

If you prefer the Dockerized database while running the backend natively, publish it on loopback only:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
```

### 2. Run Backend API
```bash
# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Development environment and bootstrap credentials
export VIGIL_ENV=development
export DATABASE_URL=postgresql://postgres:YOUR_DB_PASSWORD@127.0.0.1:5432/vigil_db
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export VIGIL_SEED_ADMIN_PASSWORD='choose-a-strong-admin-password'
export VIGIL_SEED_DEMO_USERS=true
export VIGIL_SEED_DEMO_PASSWORD='choose-a-strong-demo-password'
export VIGIL_SEED_DEMO_PATIENTS=true

# Start backend with auto-reload
PYTHONPATH=. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Swagger UI will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Run Frontend Mobile PWA
In a separate terminal:
```bash
cd mobile-app
npm install
npm run dev
```
The PWA will launch at [http://localhost:3000](http://localhost:3000).

---

## Configuration & Customization

### 1. Environment Variables (`.env`)
Copy `.env.example` to `.env` in the root directory. Relevant variables:

```env
POSTGRES_DB=vigil_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong random value>
VIGIL_APP_DB_ROLE=vigil_app
VIGIL_APP_DB_PASSWORD=<url-safe random value>
SECRET_KEY=<strong random value>

VIGIL_ENV=production
VIGIL_AUTO_SEED=false
VIGIL_SEED_ADMIN_PASSWORD=<one-time admin bootstrap password>
VIGIL_SEED_DEMO_USERS=false
VIGIL_SEED_DEMO_PASSWORD=
VIGIL_SEED_DEMO_PATIENTS=false
VIGIL_INTEGRITY_CHECK_INTERVAL_SECONDS=3600
CORS_ORIGINS=http://localhost:3001
```

`SECRET_KEY` is mandatory when `VIGIL_ENV=production`. The backend refuses to boot without it, and Postgres is not exposed to the host network by default. `VIGIL_INTEGRITY_CHECK_INTERVAL_SECONDS` controls the periodic background verification (Compose default: 3600 seconds; set `0` to disable).

### 2. Hospital Settings & Protocol Cadences
Hospital protocols are defined in [backend/config/hospital_settings.yaml](file:///Users/akshitkapoor/Documents/Health%20Care/backend/config/hospital_settings.yaml):

```yaml
protocols:
  nursing_round:
    high_acuity_interval_minutes: 120    # ICU vitals interval (2 hours)
    medium_acuity_interval_minutes: 240  # Surgical ward interval (4 hours)
    low_acuity_interval_minutes: 480     # General ward interval (8 hours)
  consent_capture:
    require_witness_for_high_risk: true
  medication_order:
    require_two_nurse_verification_for_high_alert: true
```
Modifying these thresholds directly updates the rules evaluated by the `ExpectationAgent`.

---

## Troubleshooting & FAQs

### Q: Port 5432 is already in use
**Cause:** A local PostgreSQL instance is already running on your host machine.
**Fix:** Either stop the local PostgreSQL service:
```bash
brew services stop postgresql   # macOS
sudo service postgresql stop    # Linux
```
Or, if you are using the loopback development override, change its host port in [docker-compose.dev.yml](file:///Users/akshitkapoor/Documents/Health%20Care/docker-compose.dev.yml). The default stack does not publish Postgres at all.

### Q: Port 3001 or 8000 is in use
**Fix:** Identify and stop the occupying process:
```bash
lsof -i :3001
lsof -i :8000
```
Or change the host port mapping in [docker-compose.yml](file:///Users/akshitkapoor/Documents/Health%20Care/docker-compose.yml).

### Q: Cannot connect to the Docker daemon
**Cause:** Docker Desktop is not started.
**Fix:** Open **Docker Desktop** from your Applications / Start menu and wait for the status indicator to turn green.

### Q: Backend refuses to start with an integrity error
**Cause:** The database predates the hash-chain schema, triggers are missing, or the API role lacks grants.
**Fix:** Run `python -m backend.scripts.migrate_integrity` with `MIGRATION_DATABASE_URL`, then rerun it with `--check`. Ensure `DATABASE_URL` uses the `vigil_app` role created by the migration or Docker init script. Never disable triggers to bypass this check.

### Q: Resetting the database from scratch
To wipe all state and start completely fresh:
```bash
docker compose down -v
docker compose up --build
```
Once started, run the demo seeder:
```bash
docker compose exec backend python backend/scripts/seed_comprehensive_demo.py
```

### Q: Browser shows cached / stale PWA assets
**Cause:** Service Worker aggressively caches offline assets.
**Fix:** 
1. Open DevTools (`Cmd+Option+I` on Mac, `F12` on Windows).
2. Go to the **Application** tab $\to$ **Service Workers**.
3. Check **Update on reload** and click **Unregister**.
4. Perform a hard refresh (`Cmd+Shift+R` or `Ctrl+F5`).
