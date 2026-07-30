import yaml
import os
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict, Any

from backend.event_store.models import PatientModel, WardModel, ClinicalEventModel

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "protocol_configs", "default_protocols.yaml")

class Gap:
    def __init__(self, patient_id: str, ward_id: str, rule_id: str, event_type: str, description: str, expected_time: datetime.datetime, overdue_by_mins: float):
        self.patient_id = patient_id
        self.ward_id = ward_id
        self.rule_id = rule_id
        self.event_type = event_type
        self.description = description
        self.expected_time = expected_time
        self.overdue_by_mins = overdue_by_mins

    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "ward_id": self.ward_id,
            "rule_id": self.rule_id,
            "event_type": self.event_type,
            "description": self.description,
            "expected_time": self.expected_time.isoformat(),
            "overdue_by_mins": self.overdue_by_mins
        }

class ExpectationAgent:
    """
    Deterministic rule engine that identifies clinical gaps based on YAML protocol definitions.
    """
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.protocols = self._load_protocols()

    def _load_protocols(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {"wards": {}}
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def evaluate_gaps(self, db: Session, current_time: datetime.datetime = None) -> List[Gap]:
        if current_time is None:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            
        gaps = []
        
        # 1. Get all active admitted patients
        patients = db.query(PatientModel).filter(PatientModel.status == 'admitted').all()
        
        for patient in patients:
            ward_code = patient.ward_id.split('_')[0] if '_' in patient.ward_id else patient.ward_id
            ward_rules = self.protocols.get('wards', {}).get(ward_code, {}).get('rules', [])
            
            for rule in ward_rules:
                if rule.get('trigger') == 'continuous':
                    freq_hours = rule.get('frequency_hours', 24)
                    grace_mins = rule.get('grace_period_mins', 0)
                    
                    # Find latest event of this type for this patient
                    latest_event = db.query(ClinicalEventModel).filter(
                        ClinicalEventModel.patient_id == patient.patient_id,
                        ClinicalEventModel.event_type == rule['event_type']
                    ).order_by(desc(ClinicalEventModel.device_timestamp)).first()
                    
                    # If no event, we use admission time as the baseline
                    baseline_time = latest_event.device_timestamp if latest_event else patient.admission_date
                    if not baseline_time.tzinfo:
                        baseline_time = baseline_time.replace(tzinfo=datetime.timezone.utc)
                    
                    expected_time = baseline_time + datetime.timedelta(hours=freq_hours)
                    deadline = expected_time + datetime.timedelta(minutes=grace_mins)
                    
                    if current_time > deadline:
                        overdue_by = (current_time - expected_time).total_seconds() / 60.0
                        gaps.append(Gap(
                            patient_id=patient.patient_id,
                            ward_id=patient.ward_id,
                            rule_id=rule['rule_id'],
                            event_type=rule['event_type'],
                            description=rule['description'],
                            expected_time=expected_time,
                            overdue_by_mins=round(overdue_by, 2)
                        ))
                
                # pre_procedure triggers would require tracking scheduled procedures, which is outside the current scope
                # of purely continuous monitoring, but we can add logic for it if needed later.

        return gaps
