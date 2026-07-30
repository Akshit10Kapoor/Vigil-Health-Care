import os
import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.config.settings import settings, load_hospital_settings
from backend.event_store.database import engine, Base, SessionLocal
from backend.event_store.models import WardModel, StaffModel, PatientModel
from backend.api.middleware.access_control import get_password_hash

from backend.api.routes.auth import router as auth_router
from backend.api.routes.patients import router as patients_router
from backend.api.routes.events import router as events_router
from backend.api.routes.gaps import router as gaps_router
from backend.api.routes.evidence import router as evidence_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Vigil — On-prem Clinical Event Verification System (Phase 1 API)"
)

# Configure CORS for local LAN mobile PWA and tablet devices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploaded signatures static files directory
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(patients_router, prefix=settings.API_V1_STR)
app.include_router(events_router, prefix=settings.API_V1_STR)
app.include_router(gaps_router, prefix=settings.API_V1_STR)
app.include_router(evidence_router, prefix=settings.API_V1_STR)


def seed_hospital_data():
    """Seeds wards, default staff, and sample patient records from hospital_settings.yaml if DB is empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        config = load_hospital_settings()
        
        # 1. Seed Wards
        wards_data = config.get("wards", [])
        for w in wards_data:
            existing_ward = db.query(WardModel).filter(WardModel.ward_id == w["id"]).first()
            if not existing_ward:
                new_ward = WardModel(
                    ward_id=w["id"],
                    name=w["name"],
                    acuity_level=w.get("acuity_level", "medium"),
                    capacity=w.get("capacity", 10)
                )
                db.add(new_ward)
        db.commit()

        # 2. Seed Admin & Staff Members
        seed_users = [
            {
                "staff_id": "ADMIN_01",
                "full_name": "Hospital Quality Admin",
                "role": "admin",
                "password": "AdminPassword123!",
                "assigned_ward_id": None
            },
            {
                "staff_id": "NURSE_101",
                "full_name": "Nurse Anjali Sharma",
                "role": "nurse",
                "password": "NursePassword123!",
                "assigned_ward_id": "ICU_01"
            },
            {
                "staff_id": "NURSE_102",
                "full_name": "Nurse Rajesh Kumar",
                "role": "nurse",
                "password": "NursePassword123!",
                "assigned_ward_id": "SURG_3A"
            },
            {
                "staff_id": "NURSE_103",
                "full_name": "Nurse Priya Patel",
                "role": "nurse",
                "password": "NursePassword123!",
                "assigned_ward_id": "ICU_01"
            }
        ]

        for su in seed_users:
            existing_staff = db.query(StaffModel).filter(StaffModel.staff_id == su["staff_id"]).first()
            if not existing_staff:
                hashed_pw = get_password_hash(su["password"])
                staff_user = StaffModel(
                    staff_id=su["staff_id"],
                    full_name=su["full_name"],
                    role=su["role"],
                    hashed_password=hashed_pw,
                    assigned_ward_id=su["assigned_ward_id"]
                )
                db.add(staff_user)
        db.commit()

        # 3. Seed Sample Patients for ICU and Ward testing
        sample_patients = [
            {
                "patient_id": "PAT_1001",
                "full_name": "Ramesh Verma",
                "age": 58,
                "gender": "Male",
                "bed_number": "Bed-01",
                "ward_id": "ICU_01",
                "acuity_level": "high"
            },
            {
                "patient_id": "PAT_1002",
                "full_name": "Sunita Devi",
                "age": 45,
                "gender": "Female",
                "bed_number": "Bed-03",
                "ward_id": "ICU_01",
                "acuity_level": "high"
            },
            {
                "patient_id": "PAT_2001",
                "full_name": "Vikram Singh",
                "age": 34,
                "gender": "Male",
                "bed_number": "Bed-3A-05",
                "ward_id": "SURG_3A",
                "acuity_level": "medium"
            }
        ]

        for sp in sample_patients:
            existing_pat = db.query(PatientModel).filter(PatientModel.patient_id == sp["patient_id"]).first()
            if not existing_pat:
                pat = PatientModel(
                    patient_id=sp["patient_id"],
                    full_name=sp["full_name"],
                    age=sp["age"],
                    gender=sp["gender"],
                    bed_number=sp["bed_number"],
                    ward_id=sp["ward_id"],
                    acuity_level=sp["acuity_level"],
                    status="admitted"
                )
                db.add(pat)
        db.commit()

    except Exception as e:
        print(f"Error seeding hospital data: {e}")
        db.rollback()
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    seed_hospital_data()


@app.get("/")
def root():
    return {
        "status": "online",
        "system": "Vigil Clinical Event Verification",
        "version": settings.VERSION,
        "phase": 1,
        "docs_url": "/docs"
    }
