from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
import datetime

from backend.event_store.database import get_db
from backend.event_store.models import AgentAuditLogModel
from backend.api.middleware.access_control import get_current_staff

router = APIRouter(prefix="/gaps", tags=["gaps"])

@router.get("/")
def list_gaps(
    ward_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = "open",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff)
):
    """
    Returns a list of currently detected gaps by querying the agent_audit_logs 
    for GapDetectionAgent decisions.
    In a real production system, this would be a derived view joining audit logs 
    and closure events. For this prototype, we query the audit logs directly.
    """
    
    query = db.query(AgentAuditLogModel).filter(
        AgentAuditLogModel.agent_name == "GapDetectionAgent",
        AgentAuditLogModel.action == "classify_and_describe_gap"
    )
    
    logs = query.order_by(desc(AgentAuditLogModel.timestamp)).all()
    
    results = []
    # Deduplicate by patient+rule to show only "current" state
    seen = set()
    
    for log in logs:
        input_state = log.input_state or {}
        output = log.output_decision or {}
        
        patient_id = input_state.get("patient_id")
        rule_id = input_state.get("rule_id")
        key = f"{patient_id}-{rule_id}"
        
        if key in seen:
            continue
            
        seen.add(key)
        
        g_ward_id = input_state.get("ward_id")
        g_severity = output.get("severity")
        
        if ward_id and g_ward_id != ward_id:
            continue
            
        if severity and g_severity != severity:
            continue
            
        results.append({
            "patient_id": patient_id,
            "ward_id": g_ward_id,
            "rule_id": rule_id,
            "event_type": input_state.get("event_type"),
            "expected_time": input_state.get("expected_time"),
            "overdue_by_mins": input_state.get("overdue_by_mins"),
            "severity": g_severity,
            "description": output.get("llm_description"),
            "model_version": log.model_or_rule_version,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None
        })
        
    return results

@router.post("/trigger")
def trigger_gap_detection(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_staff)
):
    """
    Manually triggers the LangGraph orchestration pipeline.
    """
    from backend.orchestration.orchestrator import trigger_verification_pipeline
    
    result = trigger_verification_pipeline()
    return {"status": "success", "classified_gaps_count": len(result.get("classified_gaps", []))}
