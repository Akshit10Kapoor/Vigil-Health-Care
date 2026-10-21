# Vigil — Local Setup & Operations Guide

This guide provides complete instructions to set up, operate, and troubleshoot the **Vigil Clinical Event Verification System** locally.

The entire stack is containerized with **Docker Compose**, allowing you to spin up the database, API server, and mobile tablet PWA with a single command. Instructions for native (bare-metal) development are also included.

---

## Table of Contents

1. [System Architecture & Container Topology](#system-architecture--container-topology)
2. [Prerequisites](#prerequisites)
3. [Quickstart: Running with Docker Compose](#quickstart-running-with-docker-compose)
4. [Service Endpoints & Access URLs](#service-endpoints--access-urls)
5. [Default Login Credentials](#default-login-credentials)
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
│                                              │ Port: 5432:5432              │   │
│                                              │ Volume: postgres_data        │   │
│                                              └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

| Service | Container Name | Port Mapping | Description |
| :--- | :--- | :--- | :--- |
| **Database** | `vigil_postgres` | `5432:5432` | PostgreSQL 16 store with append-only event schema, FK constraints, and derived SQL views. Initialized via `backend/event_store/schema/init_db.sql`. |
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

### 2. Launch the Application Stack
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
2. Execute the initial SQL schema migration (`init_db.sql`).
3. Build and launch the FastAPI backend, executing startup seeding for wards, users, and sample patients.
4. Build the PWA production assets and serve them via Node.

### 3. Check Container Status
Verify that all 3 containers are healthy and running:

```bash
docker compose ps
```

You should see:
- `vigil_postgres` (Up, healthy)
- `vigil_backend` (Up)
- `vigil_mobile_app` (Up)

### 4. View Container Logs
To follow live logs from all services:

```bash
docker compose logs -f
```

Or inspect a specific container (e.g. backend):
```bash
docker compose logs -f backend
```

### 5. Stop the Application
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
| **PostgreSQL DB** | `localhost:5432` | Database: `vigil_db`, User: `postgres`, Password: `postgrespassword` |

---

## Default Login Credentials

The database is pre-seeded with test users configured in [hospital_settings.yaml](file:///Users/akshitkapoor/Documents/Health%20Care/backend/config/hospital_settings.yaml):

| Role | Staff ID | Password | Assigned Ward | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **ICU Duty Nurse** | `NURSE_101` | `NursePassword123!` | Intensive Care Unit (`ICU_01`) | Log rounds, record vitals, capture consent, administer high-alert meds |
| **Surgical Nurse** | `NURSE_102` | `NursePassword123!` | Surgical Ward 3A (`SURG_3A`) | Surgical rounds, pre-op checklist, consent capture |
| **ICU Secondary Nurse** | `NURSE_103` | `NursePassword123!` | Intensive Care Unit (`ICU_01`) | Co-signing high-alert medication dual verification |
| **Hospital Quality Admin** | `ADMIN_01` | `AdminPassword123!` | *All Wards* | Access gap analysis, trigger verification pipelines, export NABH evidence |

---

## Populating Demo Data & Scenarios

To populate realistic clinical records and simulated compliance gaps (e.g., overdue ICU vitals, missing surgical consent):

### Running the Seed Script via Docker:
```bash
docker compose exec backend python backend/scripts/seed_comprehensive_demo.py
```

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
2. Sign in as `ADMIN_01` (Password: `AdminPassword123!`).
3. View the **Overview**:
   - Total patients admitted across wards.
   - Active Urgent & Warning clinical flags.
   - Real-time round compliance breakdown.
   - Quick navigation shortcuts via keyboard (`Cmd+K` or `Ctrl+K` opens the Command Palette).

### 2. Nursing Rounds & Vitals Logging
1. Sign in as `NURSE_101` (`NursePassword123!`).
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
2. View generated corrective action recommendations structured according to **NABH 5th Edition Chapters**:
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

---

## Alternative: Native Local Development (Without Docker)

If you prefer to run services natively without Docker containers:

### 1. Start Local PostgreSQL
Ensure PostgreSQL is running locally on port 5432 with a database named `vigil_db`:
```bash
createdb vigil_db
psql -d vigil_db -f backend/event_store/schema/init_db.sql
```

### 2. Run Backend API
```bash
# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

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
Create or edit `.env` in the root directory:

```env
# Database Connection
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5432/vigil_db

# Security
SECRET_KEY=vigil_on_prem_secret_key_2026_super_secure

# Server Config
HOST=0.0.0.0
PORT=8000

# Hospital Deployment Identity
HOSPITAL_ID=HOSP_CITY_01
HOSPITAL_NAME=City Care Super Speciality Hospital
```

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
Or edit [docker-compose.yml](file:///Users/akshitkapoor/Documents/Health%20Care/docker-compose.yml) to map to a different host port (e.g. `"5433:5432"`).

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
