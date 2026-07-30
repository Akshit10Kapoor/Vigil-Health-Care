from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from backend.event_store.database import get_db
from backend.event_store.models import PatientModel, WardModel
from backend.api.middleware.access_control import get_current_staff, StaffModel

router = APIRouter(tags=["Patients & Wards"])

class PatientCreateRequest(BaseModel):
    patient_id: str
    full_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    bed_number: str
    ward_id: str
    acuity_level: str = "medium"

class PatientResponse(BaseModel):
    patient_id: str
    full_name: str
    age: Optional[int]
    gender: Optional[str]
    bed_number: str
    ward_id: str
    acuity_level: str
    status: str

class WardResponse(BaseModel):
    ward_id: str
    name: str
    acuity_level: str
    capacity: int

@router.get("/wards", response_model=List[WardResponse])
def get_wards(db: Session = Depends(get_db)):
    wards = db.query(WardModel).filter(WardModel.is_active == True).all()
    return [
        WardResponse(
            ward_id=w.ward_id,
            name=w.name,
            acuity_level=w.acuity_level,
            capacity=w.capacity
        )
        for w in wards
    ]

@router.get("/patients", response_model=List[PatientResponse])
def get_patients(ward_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(PatientModel).filter(PatientModel.status == "admitted")
    if ward_id:
        query = query.filter(PatientModel.ward_id == ward_id)
    patients = query.all()
    return [
        PatientResponse(
            patient_id=p.patient_id,
            full_name=p.full_name,
            age=p.age,
            gender=p.gender,
            bed_number=p.bed_number,
            ward_id=p.ward_id,
            acuity_level=p.acuity_level,
            status=p.status
        )
        for p in patients
    ]

@router.post("/patients", response_model=PatientResponse)
def create_patient(
    patient_data: PatientCreateRequest,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    # Verify ward exists
    ward = db.query(WardModel).filter(WardModel.ward_id == patient_data.ward_id).first()
    if not ward:
        raise HTTPException(status_code=400, detail=f"Ward '{patient_data.ward_id}' does not exist")

    existing = db.query(PatientModel).filter(PatientModel.patient_id == patient_data.patient_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Patient ID '{patient_data.patient_id}' already registered")

    new_patient = PatientModel(
        patient_id=patient_data.patient_id,
        full_name=patient_data.full_name,
        age=patient_data.age,
        gender=patient_data.gender,
        bed_number=patient_data.bed_number,
        ward_id=patient_data.ward_id,
        acuity_level=patient_data.acuity_level,
        status="admitted"
    )
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)

    return PatientResponse(
        patient_id=new_patient.patient_id,
        full_name=new_patient.full_name,
        age=new_patient.age,
        gender=new_patient.gender,
        bed_number=new_patient.bed_number,
        ward_id=new_patient.ward_id,
        acuity_level=new_patient.acuity_level,
        status=new_patient.status
    )
