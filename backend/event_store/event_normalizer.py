import base64
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field, field_validator
from backend.config.settings import settings

class IngestedEventSchema(BaseModel):
    client_sync_id: str
    event_id: Optional[uuid.UUID] = None
    event_type: str
    patient_id: str
    ward_id: str
    bed_number: Optional[str] = None
    staff_id: str
    device_timestamp: str
    device_tz_offset: str = "+05:30"
    payload: Dict[str, Any]
    raw_note: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    corrects_event_id: Optional[uuid.UUID] = None
    correction_reason: Optional[str] = None

    @field_validator("event_type")
    def validate_event_type(cls, v):
        allowed = {
            "nursing_round",
            "consent_capture",
            "medication_order_documentation",
            "clinical_event_correction",
        }
        if v not in allowed:
            raise ValueError(f"Invalid event_type '{v}'. Allowed types: {allowed}")
        return v


def save_signature_image_if_present(event_id: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Extracts base64 signature image from payload, saves to disk blob, and replaces with signature_ref.
    """
    payload_copy = dict(payload)
    sig_data = payload_copy.pop("signature_base64", None)
    signature_ref = None

    if sig_data and isinstance(sig_data, str) and sig_data.startswith("data:image"):
        try:
            # Extract header and base64 string
            header, encoded = sig_data.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            file_name = f"sig_{event_id}_{uuid.uuid4().hex[:8]}.png"
            file_path = settings.SIGNATURE_DIR / file_name
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            signature_ref = f"/uploads/signatures/{file_name}"
            payload_copy["signature_ref"] = signature_ref
        except Exception as e:
            payload_copy["signature_error"] = str(e)
            
    return payload_copy, signature_ref


def normalize_event(event_dict: Dict[str, Any]) -> Tuple[IngestedEventSchema, Dict[str, Any]]:
    """
    Normalizes and validates an raw incoming event dictionary into canonical schema.
    """
    parsed = IngestedEventSchema(**event_dict)
    
    if not parsed.event_id:
        parsed.event_id = uuid.uuid4()
        
    cleaned_payload, sig_ref = save_signature_image_if_present(parsed.event_id, parsed.payload)
    
    return parsed, cleaned_payload
