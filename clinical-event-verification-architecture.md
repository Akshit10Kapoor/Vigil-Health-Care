# Clinical Event Verification System — Technical Architecture & Build Plan

**Product name (working):** Vigil (placeholder — rename freely)
**Scope:** Prototype for continuous verification of time-bound clinical actions (nursing rounds, consent capture, medication order documentation) with real-time gap detection and audit-evidence generation. On-prem, Gemma-based, multi-agent.

---

## 1. Design principles (read this before the architecture — it explains every decision below)

1. **Deterministic where it matters, generative where it doesn't.** Clinical protocol logic (what "should" happen and when) is rule-based and auditable. The LLM's job is language — reading messy nurse input, writing a human-readable flag, drafting a CAPA note. It never decides a clinical threshold.
2. **On-prem by default.** Patient data does not leave the hospital LAN. This is a DPDP Act argument and a sales argument simultaneously — do not architect around a cloud API call for inference.
3. **Capture layer must win on its own merits.** The tablet/app nurses use has to be faster than paper, independent of whether the compliance layer exists. If it isn't, adoption fails and there's no event data to reconcile against.
4. **Small number of agents, each with one job.** Four agents, not ten. Every additional agent is a maintenance and failure-mode cost — earn it.
5. **Everything is event-sourced.** The system's core asset is an immutable, timestamped log of clinical actions. Dashboards, gap detection, and audit evidence are all views over this log, not separate sources of truth.

---

## 2. High-level architecture (layers)

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 0 — Capture (edge, on nurse-facing devices)               │
│  Tablet/phone app: round logging, consent checklist, med orders  │
└───────────────────────────┬───────────────────────────────────────┘
                            │ (LAN, sync when connected)
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 1 — Ingestion & Event Store (on-prem server, per hospital)│
│  API gateway → event normalizer → append-only event log (DB)    │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 2 — Agent Orchestration (on-prem, same server or edge box)│
│  Orchestrator → Capture Agent → Expectation Agent →              │
│  Gap-Detection Agent → Evidence/CAPA Agent                       │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 3 — Model Serving (on-prem GPU box, local inference)      │
│  Quantized Gemma 4 served locally, no external API calls         │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 4 — Notification & Escalation                             │
│  Push/SMS to duty nurse (urgent) · daily digest to quality team  │
└───────────────────────────┬───────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 5 — Dashboard & Audit Evidence Export                     │
│  Quality-team web dashboard · NABH-mapped evidence pack export   │
└─────────────────────────────────────────────────────────────────────┘
```

Every layer runs inside the hospital's own network except optional aggregate/anonymized analytics if you later build a multi-hospital benchmarking product — keep that out of v1 entirely.

---

## 3. End-to-end pipeline (what actually happens, step by step)

1. A nurse completes a round / captures consent / logs a medication order on the tablet app. Input can be structured taps (checklist) or short free text/voice note.
2. The app timestamps and locally queues the event, syncs to the on-prem server the moment it has LAN connectivity (works offline-first — hospitals have patchy Wi-Fi in wards).
3. The **event normalizer** on the server converts raw input into a structured event record: event type, patient ID, ward, timestamp, staff ID, raw note text.
4. The **Capture Agent** (LLM-backed) processes any free-text/voice component, extracting structured fields the checklist didn't cover (e.g., a nurse's note "patient refused vitals, will retry in 30 min" gets parsed into a status + reason + follow-up flag, not just logged as "missed").
5. The **Expectation Agent** (rule engine, not LLM) holds the protocol schedule per ward/patient-acuity level: e.g., ICU vitals every 2 hours, consent required before any listed procedure, discharge summary due within 24 hours of discharge order. It continuously computes "expected event, by when" against the actual event log.
6. The **Gap-Detection Agent** reconciles expected vs. actual. Where there's a genuine gap (missed, late, or incomplete), it classifies severity using a fixed rubric (urgent / routine / documentation-only) and — this is the one place an LLM adds real value — drafts a plain-language description of the gap for a human reader.
7. The **Orchestrator** routes based on severity: urgent gaps go to Layer 4 immediately (push notification to the duty nurse/manager); routine and documentation gaps get queued into the next digest cycle.
8. The **Evidence/CAPA Agent** runs on a schedule (not real-time) over closed and open gaps, drafting corrective-action entries and structuring them against the relevant NABH chapter/objective element, so the audit-evidence pack builds itself as a byproduct of normal operation.
9. The **dashboard** presents live status per ward for the quality team, and an **export function** produces the evidence pack (organized by chapter, with timestamps and closure status) for actual survey day.

---

## 4. Tooling choices per layer (what to actually use, and why)

**Capture app (Layer 0):** Cross-platform mobile framework (Flutter or React Native) — needs to run on cheap Android tablets hospitals will actually buy, work offline, and sync later. Local SQLite for offline queueing before sync.

**API gateway / backend (Layer 1):** A standard REST API service (FastAPI or NestJS) sitting on the on-prem server. Keep this boring and well-tested — it's the reliability backbone everything else depends on.

**Event store (Layer 1):** Postgres. Event-sourced table design (append-only events table + derived/materialized views for current state), not a mutable "current status" table — you need the immutable history for both gap detection and audit evidence.

**Agent orchestration (Layer 2):** A graph-based agent framework (LangGraph is the natural fit) — lets you define the Capture → Expectation → Gap-Detection → Evidence pipeline as an explicit directed graph with clear state handoffs, rather than a loose swarm of agents calling each other unpredictably. This matters for auditability: you want to be able to show exactly which agent produced which decision, given this is feeding literal audit evidence.

**Model serving (Layer 3):** Ollama or vLLM running a quantized Gemma 4 variant on a single on-prem GPU box (this is squarely in the territory of hardware you already know from Jetson deployment work — same class of problem, resource-constrained local inference). Keep the model behind a local-only endpoint; nothing in Layer 2 should ever have an external API dependency for the core loop.

**Rule engine (Expectation Agent):** This does not need an LLM at all — a straightforward scheduling/rules library (or even a well-structured config-driven service) that maps ward + acuity + protocol to expected event cadence. Keeping this deterministic and out of the LLM's hands is the single most important architectural decision in the whole system — it's the difference between "reliable safety tool" and "hallucination-prone toy."

**Notification (Layer 4):** Firebase Cloud Messaging (push to the tablet/phone app) for urgent alerts; SMS gateway as fallback for duty staff without the app open. Keep escalation logic simple and configurable per hospital (they will want to tune thresholds).

**Dashboard (Layer 5):** A lightweight web app (React) for the quality team — ward-level live status, gap history, evidence export button. This does not need to be fancy; it needs to be trustworthy and fast to load on hospital-grade hardware/networks.

**Evidence export (Layer 5):** Generate structured documents (PDF/DOCX) mapped to NABH chapter and objective element, pulling directly from the event log and CAPA records — this is exhaust from the pipeline, not a separate manual effort.

**Observability (cross-cutting):** Structured logging across every agent step (what input, what output, what model/rule version) — non-negotiable given this system's outputs may end up in front of an external auditor. You need to be able to reconstruct why any given flag was raised, months later.

**Auth/access control (cross-cutting):** Role-based access (nurse / ward manager / quality team / hospital admin) — this is standard but do not skip it; patient data plus staff performance data in one system is sensitive on two axes at once.

---

## 5. Repo file structure

```
vigil/
├── README.md                          — what the system does, how to run it locally, architecture diagram link
├── docker-compose.yml                 — spins up backend, db, model server, dashboard for local/on-prem deployment
├── .env.example                       — config template (db creds, model endpoint, notification keys)
│
├── mobile-app/                        — nurse-facing capture app (Flutter/React Native)
│   ├── lib/
│   │   ├── screens/
│   │   │   ├── round_checklist.*      — structured round-logging UI
│   │   │   ├── consent_capture.*      — consent checklist + signature capture
│   │   │   ├── med_order_log.*        — medication order documentation UI
│   │   │   └── sync_status.*          — shows offline queue / sync state to the nurse
│   │   ├── services/
│   │   │   ├── local_db.*             — offline SQLite queue
│   │   │   ├── sync_service.*         — pushes queued events to backend when connected
│   │   │   └── auth_service.*         — staff login/session
│   │   └── models/
│   │       └── event_schema.*         — local representation matching the backend event schema
│   └── assets/                        — icons, ward/checklist config assets
│
├── backend/                           — on-prem server: API, event store, orchestration trigger
│   ├── api/
│   │   ├── routes/
│   │   │   ├── events.*               — ingest endpoint for events from mobile app
│   │   │   ├── gaps.*                 — endpoints for dashboard to read current gaps
│   │   │   ├── evidence.*             — evidence-pack export endpoint
│   │   │   └── auth.*                 — login, role management
│   │   └── middleware/
│   │       └── access_control.*       — role-based permission checks
│   ├── event_store/
│   │   ├── schema/                    — Postgres schema definitions (events, patients, staff, wards, protocols, gaps, capa)
│   │   ├── migrations/                — versioned schema migrations
│   │   └── event_normalizer.*         — converts raw mobile-app payloads into canonical event records
│   ├── orchestration/
│   │   ├── graph_definition.*         — the LangGraph pipeline: capture → expectation → gap-detection → evidence
│   │   ├── capture_agent/
│   │   │   ├── prompt_templates/      — structured extraction prompts for free-text/voice notes
│   │   │   └── agent.*                — calls the local Gemma endpoint, returns structured fields
│   │   ├── expectation_agent/
│   │   │   ├── protocol_configs/      — per-ward, per-acuity expected-event schedules (config, not code — hospital-editable)
│   │   │   └── agent.*                — deterministic rule evaluation, no LLM call
│   │   ├── gap_detection_agent/
│   │   │   ├── severity_rubric/       — fixed classification rules (urgent/routine/documentation-only)
│   │   │   └── agent.*                — reconciliation logic + LLM call for human-readable gap description
│   │   ├── evidence_agent/
│   │   │   ├── nabh_chapter_map/      — mapping of event/gap types to NABH chapter + objective element
│   │   │   └── agent.*                — drafts CAPA entries, structures evidence records
│   │   └── orchestrator.*             — routes agent outputs to notification or digest queue based on severity
│   ├── notification/
│   │   ├── push_service.*             — FCM integration
│   │   ├── sms_service.*              — SMS gateway fallback
│   │   └── digest_builder.*           — batches routine/documentation gaps into daily digest
│   └── config/
│       └── hospital_settings.*        — per-hospital thresholds, ward list, escalation rules (this system will be sold to many hospitals — every hospital-specific rule lives here, not hardcoded)
│
├── model-server/                      — local Gemma serving setup
│   ├── model_config/                  — quantization settings, which Gemma variant, context length
│   ├── serving_setup/                 — Ollama/vLLM deployment scripts and health-check config
│   └── eval/
│       ├── extraction_eval_set/       — labeled examples testing the Capture Agent's field-extraction accuracy
│       └── gap_description_eval_set/  — labeled examples testing gap-description quality/tone
│
├── dashboard/                         — quality-team facing web app (React)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ward_overview.*        — live status per ward
│   │   │   ├── gap_history.*          — historical gap log, filter by chapter/severity/status
│   │   │   └── evidence_export.*      — triggers evidence-pack generation/download
│   │   └── components/
│   │       └── (shared UI components)
│
├── evidence-export/                   — document generation for audit packs
│   ├── templates/                     — NABH-chapter-organized document templates
│   └── generator.*                    — pulls from event store + CAPA records, populates templates
│
├── infra/
│   ├── on_prem_deployment/            — docker-compose / install scripts for hospital IT to run this on their own hardware
│   └── monitoring/                    — logging config, agent decision audit trail setup
│
└── docs/
    ├── architecture.md                — this document, versioned alongside the repo
    ├── protocol_config_guide.md       — how a hospital's quality team edits expectation-agent schedules without touching code
    └── onboarding_checklist.md        — steps to deploy at a new hospital (hardware setup, ward config, staff training)
```

---

## 6. How the pieces connect (data flow contracts)

- **Mobile app → Backend API:** REST calls over the hospital LAN, authenticated per staff session, with an offline queue that retries on reconnect. Payload: raw event record (structured fields + optional free text).
- **Backend → Event Store:** Every ingested event is normalized and appended — never overwritten. Current-state views (e.g., "last round for patient X") are computed from this log, not stored separately.
- **Event Store → Orchestration graph:** New events trigger the orchestration pipeline (event-driven, not polling — use a lightweight message queue or Postgres LISTEN/NOTIFY to avoid a full message-broker dependency at prototype stage).
- **Capture Agent ↔ Model Server:** Local HTTP call to the Gemma endpoint, structured-output prompting (ask for JSON, validate against schema before accepting).
- **Expectation Agent:** Reads from `protocol_configs`, queries the event store for the relevant patient/ward's actual event history, computes gaps — no external call needed.
- **Gap-Detection Agent → Model Server:** Only called once a gap is confirmed by the deterministic reconciliation — the LLM never decides *whether* a gap exists, only how to describe/classify severity within the fixed rubric.
- **Orchestrator → Notification layer:** Urgent classification triggers immediate push/SMS; everything else writes to a digest table read once daily by `digest_builder`.
- **Evidence Agent → Evidence Export:** Runs on a schedule (e.g., nightly), writes structured CAPA/evidence records back into the event store, which `evidence-export/generator` later reads to populate the actual document templates on demand.
- **Dashboard → Backend API:** Read-only endpoints for gap history and ward status; a separate authenticated endpoint triggers evidence-pack generation.

---

## 7. Build order for the prototype (do not build top to bottom of the architecture — build in this order)

1. **Mobile capture app + backend ingestion + event store only.** No agents yet. Get this into one ward, prove nurses will use it over paper. This alone is validation-critical.
2. **Expectation Agent (rule engine) against real logged events.** Now you have real data to build the schedule-reconciliation logic against, not imagined data.
3. **Gap-Detection Agent + Orchestrator + Notification.** This is the first point where "the system tells someone something useful in real time" — your actual demo moment.
4. **Capture Agent (LLM field extraction from free text).** Add this once the structured-checklist path is solid; free-text handling is a refinement, not a blocker.
5. **Evidence/CAPA Agent + export.** Build last — it's valuable but not urgent, and you want real gap data accumulated before designing the evidence templates around it.

---

## 8. What to explicitly not build in the prototype

- No multi-hospital benchmarking or cross-hospital analytics — single-tenant, on-prem, one hospital's data never touches another's infrastructure.
- No full EMR/HIS integration — the mobile capture app is your data source; treat any future HIS integration as a v2 nice-to-have, not a dependency.
- No coverage of all 10 NABH chapters — rounds, consent, medication documentation only, per the wedge already agreed.
- No attempt to have the LLM adjudicate clinical correctness — it structures, describes, and drafts; the rule engine and human staff decide.
