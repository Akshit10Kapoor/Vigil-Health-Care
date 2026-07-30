from sqlalchemy.orm import Session
from typing import Dict, Any, List

from backend.orchestration.expectation_agent.agent import Gap
from backend.orchestration.llm_client import LLMClient
from backend.event_store.models import AgentAuditLogModel

class GapDetectionAgent:
    """
    Classifies gap severity using deterministic rules, then uses the LLM to write a 
    human-readable description of the gap.
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
        
    def classify_severity(self, gap: Gap) -> str:
        """
        Deterministic severity rubric.
        - Urgent: overdue > 60 mins for vitals/meds, or > 0 mins for consent before procedure.
        - Routine: overdue between 0-60 mins for standard protocols.
        - Documentation-Only: not overdue, but missing required signatures or fields.
        """
        if gap.event_type == 'consent':
            return 'Urgent'
            
        if gap.overdue_by_mins > 60:
            return 'Urgent'
        elif gap.overdue_by_mins > 0:
            return 'Routine'
        else:
            return 'Documentation-Only'

    def process_gaps(self, db: Session, gaps: List[Gap]) -> List[Dict[str, Any]]:
        processed = []
        
        for gap in gaps:
            # 1. Deterministic classification
            severity = self.classify_severity(gap)
            
            # 2. LLM Description Draft
            gap_dict = gap.to_dict()
            description, model_version = self.llm_client.describe_gap(gap_dict)
            
            # Combine
            result = {
                **gap_dict,
                "severity": severity,
                "llm_description": description,
                "model_version": model_version
            }
            
            # 3. Audit Log
            audit = AgentAuditLogModel(
                agent_name="GapDetectionAgent",
                action="classify_and_describe_gap",
                input_state=gap_dict,
                output_decision={"severity": severity, "llm_description": description},
                model_or_rule_version=model_version
            )
            db.add(audit)
            processed.append(result)
            
        db.commit()
        return processed
