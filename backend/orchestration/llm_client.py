from typing import Dict, Any, Tuple

class LLMClient:
    """
    Simulated LLM Client for local prototyping.
    In production, this would make HTTP calls to a local Gemma/vLLM server.
    """
    
    @staticmethod
    def extract_fields(raw_note: str) -> Tuple[Dict[str, Any], str]:
        """
        Simulates extracting structured fields from a messy nurse note.
        Returns a tuple of (extracted_fields, model_version)
        """
        # Dynamic template filling based on naive keyword matching
        extracted = {}
        note_lower = raw_note.lower()
        
        if "bp" in note_lower or "blood pressure" in note_lower:
            # Fake parsing just to show dynamic behavior
            extracted["vitals.bp"] = "120/80 (extracted)"
        if "hr" in note_lower or "heart rate" in note_lower:
            extracted["vitals.hr"] = 85
            
        if "refused" in note_lower:
            extracted["status"] = "refused"
            extracted["reason"] = "Patient refused based on note"
        elif "asleep" in note_lower:
            extracted["status"] = "delayed"
            extracted["reason"] = "Patient asleep"
            
        return extracted, "stub-v1"

    @staticmethod
    def describe_gap(gap_details: Dict[str, Any]) -> Tuple[str, str]:
        """
        Simulates drafting a human-readable description of a gap.
        Returns a tuple of (description, model_version)
        """
        event_type = gap_details.get("event_type", "event")
        overdue = gap_details.get("overdue_by_mins", 0)
        rule_desc = gap_details.get("description", "required protocol")
        
        # Dynamic response based on input
        if overdue > 60:
            desc = f"Critical delay: {event_type} is overdue by over an hour ({overdue} mins). Protocol '{rule_desc}' violated."
        elif overdue > 0:
            desc = f"{event_type.capitalize()} missed: Overdue by {overdue} mins per '{rule_desc}'."
        else:
            desc = f"Pending {event_type} per '{rule_desc}'."
            
        return desc, "stub-v1"

    @staticmethod
    def draft_capa(gap_details: Dict[str, Any], evidence_history: list) -> Tuple[str, str]:
        """
        Simulates drafting a CAPA (Corrective and Preventive Action) note.
        """
        desc = gap_details.get("description", "Unknown gap")
        ward = gap_details.get("ward_id", "Unknown Ward")
        
        capa_text = f"CAPA DRAFT: Issue logged in {ward} regarding '{desc}'. "
        capa_text += "Action taken: Staff re-educated on timing requirements. "
        capa_text += f"Prior history indicates {len(evidence_history)} related events."
        
        return capa_text, "stub-v1"

