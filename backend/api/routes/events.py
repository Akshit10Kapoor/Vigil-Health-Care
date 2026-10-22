import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.middleware.access_control import get_current_staff
from backend.event_store.database import get_db
from backend.event_store.event_normalizer import normalize_event
from backend.event_store.integrity import ChainIntegrityError, append_clinical_event
from backend.event_store.models import (
    AgentAuditLogModel,
    ClinicalEventModel,
    PatientModel,
    StaffModel,
    WardModel,
)
from backend.orchestration.capture_agent.agent import CaptureAgent

router = APIRouter(prefix="/events", tags=["Event Store Ingestion & Views"])

MAX_CHAIN_ATTEMPTS = 5


class EventIngestRequest(BaseModel):
    events: List[Dict[str, Any]]


class ItemIngestResult(BaseModel):
    client_sync_id: str
    status: str
    event_id: Optional[str] = None
    error_message: Optional[str] = None


class BatchIngestResponse(BaseModel):
    total: int
    success_count: int
    failed_count: int
    results: List[ItemIngestResult]


def _duplicate_result(existing: ClinicalEventModel) -> ItemIngestResult:
    return ItemIngestResult(
        client_sync_id=existing.client_sync_id,
        status="duplicate",
        event_id=str(existing.event_id) if existing.event_id else None,
        error_message=None,
    )


def _ingest_one(db: Session, raw_event: Dict[str, Any]) -> ItemIngestResult:
    sync_id = raw_event.get("client_sync_id", "unknown_sync_id")
    last_error: Optional[Exception] = None

    for attempt in range(MAX_CHAIN_ATTEMPTS):
        try:
            existing = (
                db.query(ClinicalEventModel)
                .filter(ClinicalEventModel.client_sync_id == sync_id)
                .first()
            )
            if existing:
                return _duplicate_result(existing)

            parsed_event, cleaned_payload = normalize_event(raw_event)

            ward = (
                db.query(WardModel)
                .filter(WardModel.ward_id == parsed_event.ward_id)
                .first()
            )
            if not ward:
                raise ValueError(
                    f"Ward '{parsed_event.ward_id}' not found in registry"
                )

            patient = (
                db.query(PatientModel)
                .filter(PatientModel.patient_id == parsed_event.patient_id)
                .first()
            )
            if not patient:
                raise ValueError(
                    f"Patient '{parsed_event.patient_id}' not found in registry"
                )

            staff = (
                db.query(StaffModel)
                .filter(StaffModel.staff_id == parsed_event.staff_id)
                .first()
            )
            if not staff:
                raise ValueError(
                    f"Staff member '{parsed_event.staff_id}' not found in registry"
                )

            try:
                device_ts = datetime.datetime.fromisoformat(
                    parsed_event.device_timestamp.replace("Z", "+00:00")
                )
            except Exception:
                device_ts = datetime.datetime.now(datetime.timezone.utc)
            if device_ts.tzinfo is None:
                device_ts = device_ts.replace(tzinfo=datetime.timezone.utc)

            event_record = ClinicalEventModel(
                event_id=parsed_event.event_id,
                event_type=parsed_event.event_type,
                patient_id=parsed_event.patient_id,
                ward_id=parsed_event.ward_id,
                bed_number=parsed_event.bed_number or patient.bed_number,
                staff_id=parsed_event.staff_id,
                device_timestamp=device_ts,
                device_tz_offset=parsed_event.device_tz_offset,
                payload=cleaned_payload,
                raw_note=parsed_event.raw_note,
                client_sync_id=parsed_event.client_sync_id,
                metadata_info=parsed_event.metadata,
                corrects_event_id=parsed_event.corrects_event_id,
                correction_reason=parsed_event.correction_reason,
            )

            capture_agent = CaptureAgent()
            extraction = capture_agent.extract_into_event(event_record)
            append_clinical_event(db, event_record)
            if extraction:
                capture_agent.record_extraction_audit(
                    db, event_record, extraction
                )

            audit_log = AgentAuditLogModel(
                agent_name="IngestionNormalizer",
                event_id=event_record.event_id,
                action="INGEST_CLINICAL_EVENT",
                input_state={
                    "client_sync_id": sync_id,
                    "event_type": parsed_event.event_type,
                },
                output_decision={
                    "status": "INGESTED",
                    "event_id": str(event_record.event_id),
                    "event_hash": event_record.event_hash,
                },
                model_or_rule_version="v1.1.0-phase1a",
            )
            db.add(audit_log)
            db.commit()

            return ItemIngestResult(
                client_sync_id=sync_id,
                status="success",
                event_id=str(event_record.event_id),
                error_message=None,
            )

        except IntegrityError as err:
            db.rollback()
            existing = (
                db.query(ClinicalEventModel)
                .filter(ClinicalEventModel.client_sync_id == sync_id)
                .first()
            )
            if existing:
                return _duplicate_result(existing)
            last_error = err
            message = str(getattr(err, "orig", err)).lower()
            if "prev_hash" in message and attempt < MAX_CHAIN_ATTEMPTS - 1:
                continue
            break
        except ChainIntegrityError as err:
            db.rollback()
            last_error = err
            break
        except Exception as err:
            db.rollback()
            last_error = err
            break

    return ItemIngestResult(
        client_sync_id=sync_id,
        status="error",
        event_id=raw_event.get("event_id"),
        error_message=str(last_error) if last_error else "Ingestion failed",
    )


@router.post("/ingest", response_model=BatchIngestResponse)
def ingest_events(request: EventIngestRequest, db: Session = Depends(get_db)):
    results = []
    success_count = 0
    failed_count = 0

    for raw_event in request.events:
        result = _ingest_one(db, raw_event)
        results.append(result)
        if result.status in {"success", "duplicate"}:
            success_count += 1
        else:
            failed_count += 1

    return BatchIngestResponse(
        total=len(request.events),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


@router.get("", response_model=List[Dict[str, Any]])
def get_events(
    ward_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff),
):
    query = db.query(ClinicalEventModel)
    if ward_id:
        query = query.filter(ClinicalEventModel.ward_id == ward_id)
    if patient_id:
        query = query.filter(ClinicalEventModel.patient_id == patient_id)
    if event_type:
        query = query.filter(ClinicalEventModel.event_type == event_type)

    events = (
        query.order_by(ClinicalEventModel.device_timestamp.desc()).limit(limit).all()
    )

    return [
        {
            "id": e.id,
            "event_id": e.event_id,
            "event_type": e.event_type,
            "patient_id": e.patient_id,
            "ward_id": e.ward_id,
            "bed_number": e.bed_number,
            "staff_id": e.staff_id,
            "device_timestamp": e.device_timestamp.isoformat()
            if e.device_timestamp
            else None,
            "device_tz_offset": e.device_tz_offset,
            "ingested_at": e.ingested_at.isoformat() if e.ingested_at else None,
            "payload": e.payload,
            "raw_note": e.raw_note,
            "client_sync_id": e.client_sync_id,
            "prev_hash": e.prev_hash,
            "event_hash": e.event_hash,
            "corrects_event_id": e.corrects_event_id,
            "correction_reason": e.correction_reason,
        }
        for e in events
    ]


@router.get("/views/latest-rounds")
def get_latest_rounds(ward_id: Optional[str] = None, db: Session = Depends(get_db)):
    sql = """
        SELECT e.patient_id, e.ward_id, e.bed_number, e.staff_id,
               e.device_timestamp AS last_round_timestamp, e.payload, e.raw_note
        FROM clinical_events e
        INNER JOIN (
            SELECT patient_id, MAX(device_timestamp) as max_ts
            FROM clinical_events
            WHERE event_type = 'nursing_round'
            GROUP BY patient_id
        ) latest ON e.patient_id = latest.patient_id AND e.device_timestamp = latest.max_ts
        WHERE e.event_type = 'nursing_round'
    """
    params = {}
    if ward_id:
        sql += " AND e.ward_id = :ward_id"
        params["ward_id"] = ward_id

    result = db.execute(text(sql), params).fetchall()

    import json

    rounds_out = []
    for r in result:
        payload_data = r.payload
        if isinstance(payload_data, str):
            try:
                payload_data = json.loads(payload_data)
            except Exception:
                pass

        rounds_out.append(
            {
                "patient_id": r.patient_id,
                "ward_id": r.ward_id,
                "bed_number": r.bed_number,
                "staff_id": r.staff_id,
                "last_round_timestamp": r.last_round_timestamp,
                "payload": payload_data,
                "raw_note": r.raw_note,
            }
        )

    return rounds_out
