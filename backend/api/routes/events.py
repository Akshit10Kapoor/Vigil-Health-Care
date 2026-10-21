import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.event_store.database import get_db
from backend.event_store.models import (
    ClinicalEventModel, PatientModel, WardModel, StaffModel, AgentAuditLogModel
)
from backend.event_store.event_normalizer import normalize_event
from backend.api.middleware.access_control import get_current_staff

router = APIRouter(prefix="/events", tags=["Event Store Ingestion & Views"])

class EventIngestRequest(BaseModel):
    events: List[Dict[str, Any]]

class ItemIngestResult(BaseModel):
    client_sync_id: str
    status: str # 'success', 'duplicate', 'error'
    event_id: Optional[str] = None
    error_message: Optional[str] = None

class BatchIngestResponse(BaseModel):
    total: int
    success_count: int
    failed_count: int
    results: List[ItemIngestResult]

@router.post("/ingest", response_model=BatchIngestResponse)
def ingest_events(
    request: EventIngestRequest,
    db: Session = Depends(get_db)
):
    results = []
    success_count = 0
    failed_count = 0

    for raw_event in request.events:
        sync_id = raw_event.get("client_sync_id", "unknown_sync_id")
        
        # Check for idempotency (duplicate client_sync_id)
        existing = db.query(ClinicalEventModel).filter(ClinicalEventModel.client_sync_id == sync_id).first()
        if existing:
            results.append(ItemIngestResult(
                client_sync_id=sync_id,
                status="duplicate",
                event_id=str(existing.event_id) if existing.event_id else None,
                error_message=None
            ))
            success_count += 1
            continue

        try:
            # 1. Normalize & Validate Schema
            parsed_event, cleaned_payload = normalize_event(raw_event)

            # 2. Validate Ward reference
            ward = db.query(WardModel).filter(WardModel.ward_id == parsed_event.ward_id).first()
            if not ward:
                raise ValueError(f"Ward '{parsed_event.ward_id}' not found in registry")

            # 3. Validate Patient reference
            patient = db.query(PatientModel).filter(PatientModel.patient_id == parsed_event.patient_id).first()
            if not patient:
                raise ValueError(f"Patient '{parsed_event.patient_id}' not found in registry")

            # 4. Validate Staff reference
            staff = db.query(StaffModel).filter(StaffModel.staff_id == parsed_event.staff_id).first()
            if not staff:
                raise ValueError(f"Staff member '{parsed_event.staff_id}' not found in registry")

            # Parse device timestamp
            try:
                device_ts = datetime.datetime.fromisoformat(parsed_event.device_timestamp)
            except Exception:
                device_ts = datetime.datetime.utcnow()

            # 5. Insert into Append-Only Event Store
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
                metadata_info=parsed_event.metadata
            )
            
            db.add(event_record)
            db.flush() # Ensure event exists for foreign keys
            
            from backend.orchestration.capture_agent.agent import CaptureAgent
            capture_agent = CaptureAgent()
            event_record = capture_agent.process_event(db, event_record)

            # 6. Record Audit Log Entry
            audit_log = AgentAuditLogModel(
                agent_name="IngestionNormalizer",
                event_id=parsed_event.event_id,
                action="INGEST_CLINICAL_EVENT",
                input_state={"client_sync_id": sync_id, "event_type": parsed_event.event_type},
                output_decision={"status": "INGESTED", "event_id": parsed_event.event_id},
                model_or_rule_version="v1.0.0-phase1"
            )
            db.add(audit_log)

            db.commit()

            results.append(ItemIngestResult(
                client_sync_id=sync_id,
                status="success",
                event_id=parsed_event.event_id,
                error_message=None
            ))
            success_count += 1

        except Exception as err:
            db.rollback()
            failed_count += 1
            results.append(ItemIngestResult(
                client_sync_id=sync_id,
                status="error",
                event_id=raw_event.get("event_id"),
                error_message=str(err)
            ))

    return BatchIngestResponse(
        total=len(request.events),
        success_count=success_count,
        failed_count=failed_count,
        results=results
    )


@router.get("", response_model=List[Dict[str, Any]])
def get_events(
    ward_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    query = db.query(ClinicalEventModel)
    if ward_id:
        query = query.filter(ClinicalEventModel.ward_id == ward_id)
    if patient_id:
        query = query.filter(ClinicalEventModel.patient_id == patient_id)
    if event_type:
        query = query.filter(ClinicalEventModel.event_type == event_type)

    events = query.order_by(ClinicalEventModel.device_timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": e.id,
            "event_id": e.event_id,
            "event_type": e.event_type,
            "patient_id": e.patient_id,
            "ward_id": e.ward_id,
            "bed_number": e.bed_number,
            "staff_id": e.staff_id,
            "device_timestamp": e.device_timestamp.isoformat() if e.device_timestamp else None,
            "device_tz_offset": e.device_tz_offset,
            "ingested_at": e.ingested_at.isoformat() if e.ingested_at else None,
            "payload": e.payload,
            "raw_note": e.raw_note,
            "client_sync_id": e.client_sync_id
        }
        for e in events
    ]


@router.get("/views/latest-rounds")
def get_latest_rounds(ward_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Returns latest nursing rounds per patient calculated from append-only event log.
    """
    # Subquery for latest round timestamp per patient
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
    if ward_id:
        sql += f" AND e.ward_id = '{ward_id}'"
        
    result = db.execute(text(sql)).fetchall()
    
    import json
    
    rounds_out = []
    for r in result:
        payload_data = r.payload
        if isinstance(payload_data, str):
            try:
                payload_data = json.loads(payload_data)
            except Exception:
                pass
                
        rounds_out.append({
            "patient_id": r.patient_id,
            "ward_id": r.ward_id,
            "bed_number": r.bed_number,
            "staff_id": r.staff_id,
            "last_round_timestamp": r.last_round_timestamp,
            "payload": payload_data,
            "raw_note": r.raw_note
        })
        
    return rounds_out

