import datetime
from backend.orchestration.graph_definition import create_pipeline_graph

def trigger_verification_pipeline(current_time: datetime.datetime = None):
    """
    Triggers the LangGraph orchestration pipeline for Gap Detection.
    """
    if current_time is None:
        current_time = datetime.datetime.now(datetime.timezone.utc)
        
    pipeline = create_pipeline_graph()
    
    initial_state = {
        "current_time": current_time,
        "detected_gaps": [],
        "classified_gaps": []
    }
    
    # Run the graph
    result = pipeline.invoke(initial_state)
    return result

if __name__ == "__main__":
    trigger_verification_pipeline()
