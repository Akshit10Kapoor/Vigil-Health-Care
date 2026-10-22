import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from backend.event_store.models import AgentAuditLogModel, ClinicalEventModel
from backend.orchestration.llm_client import LLMClient

logger = logging.getLogger(__name__)


class CaptureAgent:
    def __init__(self):
        self.llm_client = LLMClient()

    def extract_into_event(
        self, event: ClinicalEventModel
    ) -> Optional[Tuple[Dict[str, Any], str]]:
        if not event.raw_note:
            return None

        extracted_fields, model_version = self.llm_client.extract_fields(event.raw_note)
        if not extracted_fields:
            return None

        current_payload = event.payload if event.payload else {}
        if "extracted" not in current_payload:
            current_payload["extracted"] = {}
        current_payload["extracted"].update(extracted_fields)
        event.payload = current_payload
        return extracted_fields, model_version

    def record_extraction_audit(
        self,
        db: Session,
        event: ClinicalEventModel,
        extraction: Tuple[Dict[str, Any], str],
    ) -> AgentAuditLogModel:
        extracted_fields, model_version = extraction
        audit = AgentAuditLogModel(
            agent_name="CaptureAgent",
            action="extract_fields_from_note",
            event_id=event.event_id,
            input_state={"raw_note": event.raw_note},
            output_decision={"extracted_fields": extracted_fields},
            model_or_rule_version=model_version,
        )
        db.add(audit)
        return audit

    def process_event(self, db: Session, event: ClinicalEventModel) -> ClinicalEventModel:
        extraction = self.extract_into_event(event)
        if extraction:
            self.record_extraction_audit(db, event, extraction)
        return event
