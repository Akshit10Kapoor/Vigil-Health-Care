import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.event_store.database import SessionLocal
from backend.orchestration.expectation_agent.agent import ExpectationAgent

db = SessionLocal()
agent = ExpectationAgent()
gaps = agent.evaluate_gaps(db)
print("GAPS:", gaps)
for g in gaps:
    print(g.to_dict())
