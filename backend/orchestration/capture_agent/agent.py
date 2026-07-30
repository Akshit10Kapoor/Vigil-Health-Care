import json
import logging
from sqlalchemy.orm import Session
from backend.orchestration.llm_client import LLMClient
from backend.event_store.models import AgentAuditLogModel, ClinicalEventModel

logger = logging.getLogger(__name__)

class CaptureAgent:
    """
    Processes free-text/voice notes attached to clinical events and extracts
    structured fields using the LLM.
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
        
    def process_event(self, db: Session, event: ClinicalEventModel) -> ClinicalEventModel:
        if not event.raw_note:
            return event
            
        # 1. LLM Extraction
        extracted_fields, model_version = self.llm_client.extract_fields(event.raw_note)
        
        if not extracted_fields:
            return event
            
        # 2. Update Payload (appending extracted fields)
        current_payload = event.payload if event.payload else {}
        
        # Merge extracted fields into payload. In a real system, you'd want Pydantic schema validation here.
        # We will nest them under an 'extracted' key to separate them from deterministic checklist fields.
        if "extracted" not in current_payload:
            current_payload["extracted"] = {}
            
        current_payload["extracted"].update(extracted_fields)
        event.payload = current_payload
        
        # 3. Audit Log
        audit = AgentAuditLogModel(
            agent_name="CaptureAgent",
            action="extract_fields_from_note",
            event_id=event.event_id,
            input_state={"raw_note": event.raw_note},
            output_decision={"extracted_fields": extracted_fields},
            model_or_rule_version=model_version
        )
        db.add(audit)
        
        # We don't commit here, we assume the caller (event normalizer or API) commits
        return event
