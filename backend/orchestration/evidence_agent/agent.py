import os
import json
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.orchestration.llm_client import LLMClient
from backend.event_store.models import AgentAuditLogModel

MAP_PATH = os.path.join(os.path.dirname(__file__), "nabh_chapter_map", "chapters.json")

class EvidenceAgent:
    """
    Drafts CAPA entries for gaps and structures them against NABH chapters.
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
        standards = self._load_nabh_standards()
        self.edition = standards.get("edition", "6th")
        self.chapters = standards.get("chapters", {})
        self.chapter_map = standards.get("event_map", standards)

    def _load_nabh_standards(self) -> Dict[str, Any]:
        if not os.path.exists(MAP_PATH):
            return {}
        with open(MAP_PATH, "r") as f:
            return json.load(f)

    def _map_event_to_nabh(self, event_type: str) -> Dict[str, Any]:
        mapping = self.chapter_map.get(event_type, {"chapter": "GEN", "element": "General"})
        chapter_code = mapping.get("chapter")
        chapter = self.chapters.get(chapter_code, {})
        return {
            **mapping,
            "chapter_name": chapter.get("name", mapping.get("element")),
            "edition": self.edition,
        }

    def process_closed_gaps(self, db: Session):
        """
        In a full system, this would query closed gaps.
        For this prototype, we'll fetch all processed gaps from the audit log
        and generate a CAPA draft for them.
        """
        # Fetch classified gaps from audit log
        logs = db.query(AgentAuditLogModel).filter(
            AgentAuditLogModel.agent_name == "GapDetectionAgent"
        ).all()
        
        for log in logs:
            gap_details = log.input_state
            
            # Don't process if CAPA was already generated
            existing_capa = db.query(AgentAuditLogModel).filter(
                AgentAuditLogModel.agent_name == "EvidenceAgent",
                AgentAuditLogModel.event_id == log.event_id
            ).first()
            
            if existing_capa:
                continue
                
            # 1. Structure against NABH chapter
            event_type = gap_details.get("event_type", "unknown")
            nabh_mapping = self._map_event_to_nabh(event_type)
            
            # 2. LLM Drafts CAPA
            # We would normally query past history to pass into the LLM, simulating a few past events here.
            evidence_history = [1, 2, 3] 
            
            capa_text, model_version = self.llm_client.draft_capa(gap_details, evidence_history)
            
            # 3. Audit Log
            audit = AgentAuditLogModel(
                agent_name="EvidenceAgent",
                action="draft_capa",
                event_id=log.event_id,
                input_state=gap_details,
                output_decision={
                    "nabh_mapping": nabh_mapping,
                    "capa_draft": capa_text
                },
                model_or_rule_version=model_version
            )
            db.add(audit)
            
        db.commit()
