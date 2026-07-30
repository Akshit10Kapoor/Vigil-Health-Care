from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from backend.orchestration.expectation_agent.agent import ExpectationAgent
from backend.orchestration.gap_detection_agent.agent import GapDetectionAgent
from backend.notification.push_service import PushService
from backend.notification.sms_service import SMSService
from backend.notification.digest_builder import DigestBuilder
from backend.event_store.database import SessionLocal

class PipelineState(TypedDict):
    current_time: Any
    detected_gaps: List[Any]
    classified_gaps: List[Dict[str, Any]]

def run_expectation_agent(state: PipelineState) -> PipelineState:
    db = SessionLocal()
    try:
        agent = ExpectationAgent()
        gaps = agent.evaluate_gaps(db, state.get("current_time"))
        return {"detected_gaps": gaps}
    finally:
        db.close()

def run_gap_detection_agent(state: PipelineState) -> PipelineState:
    db = SessionLocal()
    try:
        if not state.get("detected_gaps"):
            return {"classified_gaps": []}
            
        agent = GapDetectionAgent()
        classified = agent.process_gaps(db, state["detected_gaps"])
        return {"classified_gaps": classified}
    finally:
        db.close()

def run_notification_router(state: PipelineState) -> PipelineState:
    for gap in state.get("classified_gaps", []):
        severity = gap.get("severity")
        if severity == "Urgent":
            # Real implementation would look up duty nurse by ward_id
            PushService.send_urgent_push("DUTY_NURSE_1", gap.get("llm_description"))
            SMSService.send_sms_fallback("+1234567890", gap.get("llm_description"))
        else:
            DigestBuilder.queue_for_digest(gap)
    return state

def create_pipeline_graph():
    workflow = StateGraph(PipelineState)
    
    workflow.add_node("expectation", run_expectation_agent)
    workflow.add_node("gap_detection", run_gap_detection_agent)
    workflow.add_node("notification", run_notification_router)
    
    workflow.set_entry_point("expectation")
    workflow.add_edge("expectation", "gap_detection")
    workflow.add_edge("gap_detection", "notification")
    workflow.add_edge("notification", END)
    
    return workflow.compile()
