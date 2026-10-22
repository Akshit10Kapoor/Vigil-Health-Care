import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.config.settings import settings, load_hospital_settings
from backend.event_store.database import engine, Base, SessionLocal
from backend.event_store.integrity import (
    assert_integrity_ready,
    clear_integrity_failure,
    ensure_chain_state,
    install_integrity_triggers,
    mark_integrity_failure,
    record_verification,
    verify_chain,
)
from backend.event_store.models import WardModel, StaffModel, PatientModel
from backend.api.middleware.access_control import get_password_hash

from backend.api.routes.auth import router as auth_router
from backend.api.routes.patients import router as patients_router
from backend.api.routes.events import router as events_router
from backend.api.routes.gaps import router as gaps_router
from backend.api.routes.evidence import router as evidence_router
from backend.api.routes.integrity import router as integrity_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Vigil - On-prem Clinical Event Verification System (Phase 1 API)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(patients_router, prefix=settings.API_V1_STR)
app.include_router(events_router, prefix=settings.API_V1_STR)
app.include_router(gaps_router, prefix=settings.API_V1_STR)
app.include_router(evidence_router, prefix=settings.API_V1_STR)
app.include_router(integrity_router, prefix=settings.API_V1_STR)


def _seed_wards(db: Session, config: dict):
    for ward in config.get("wards", []):
        existing_ward = db.query(WardModel).filter(WardModel.ward_id == ward["id"]).first()
        if not existing_ward:
            db.add(WardModel(
                ward_id=ward["id"],
                name=ward["name"],
                acuity_level=ward.get("acuity_level", "medium"),
                capacity=ward.get("capacity", 10)
            ))
    db.commit()


def _seed_staff(db: Session, config: dict):
    initial_seed = config.get("initial_seed", {})
    admin_user = initial_seed.get("admin_user")

    if admin_user and settings.SEED_ADMIN_PASSWORD:
        if len(settings.SEED_ADMIN_PASSWORD) < 12:
            raise ValueError("VIGIL_SEED_ADMIN_PASSWORD must be at least 12 characters")
        existing = db.query(StaffModel).filter(StaffModel.staff_id == admin_user["staff_id"]).first()
        if not existing:
            db.add(StaffModel(
                staff_id=admin_user["staff_id"],
                full_name=admin_user["full_name"],
                role=admin_user.get("role", "admin"),
                hashed_password=get_password_hash(settings.SEED_ADMIN_PASSWORD),
                assigned_ward_id=admin_user.get("assigned_ward_id")
            ))
    elif admin_user:
        print("Skipping admin seed: set VIGIL_SEED_ADMIN_PASSWORD to bootstrap the first admin")

    if not settings.SEED_DEMO_USERS:
        db.commit()
        return

    if not settings.SEED_DEMO_PASSWORD:
        print("Skipping demo staff seed: set VIGIL_SEED_DEMO_PASSWORD or disable VIGIL_SEED_DEMO_USERS")
        db.commit()
        return

    if len(settings.SEED_DEMO_PASSWORD) < 12:
        raise ValueError("VIGIL_SEED_DEMO_PASSWORD must be at least 12 characters")

    for demo_user in initial_seed.get("demo_users", []):
        existing = db.query(StaffModel).filter(StaffModel.staff_id == demo_user["staff_id"]).first()
        if not existing:
            db.add(StaffModel(
                staff_id=demo_user["staff_id"],
                full_name=demo_user["full_name"],
                role=demo_user["role"],
                hashed_password=get_password_hash(settings.SEED_DEMO_PASSWORD),
                assigned_ward_id=demo_user.get("assigned_ward_id")
            ))
    db.commit()


def _seed_sample_patients(db: Session):
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

    for patient in sample_patients:
        existing_patient = db.query(PatientModel).filter(PatientModel.patient_id == patient["patient_id"]).first()
        if not existing_patient:
            db.add(PatientModel(
                patient_id=patient["patient_id"],
                full_name=patient["full_name"],
                age=patient["age"],
                gender=patient["gender"],
                bed_number=patient["bed_number"],
                ward_id=patient["ward_id"],
                acuity_level=patient["acuity_level"],
                status="admitted"
            ))
    db.commit()


def seed_hospital_data():
    db = SessionLocal()
    try:
        config = load_hospital_settings()
        _seed_wards(db, config)
        _seed_staff(db, config)
        if settings.SEED_DEMO_PATIENTS:
            _seed_sample_patients(db)
    except Exception as e:
        print(f"Error seeding hospital data: {e}")
        db.rollback()
        if isinstance(e, ValueError):
            raise
    finally:
        db.close()


def _run_integrity_check():
    db = SessionLocal()
    try:
        result = verify_chain(db)
        record_verification(db, result)
        return result
    finally:
        db.close()


async def _integrity_loop(interval_seconds: int):
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            result = await asyncio.to_thread(_run_integrity_check)
            if result.valid:
                clear_integrity_failure()
            else:
                reason = (
                    f"{result.reason} at event {result.first_invalid_event_id}"
                )
                mark_integrity_failure(reason)
                logger.error("Integrity verification failed: %s", reason)
        except Exception as exc:
            mark_integrity_failure(f"scheduled verification crashed: {exc}")
            logger.exception("Scheduled integrity verification crashed")


_integrity_task = None


@app.on_event("startup")
async def startup_event():
    global _integrity_task

    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            ensure_chain_state(db)
        finally:
            db.close()
        install_integrity_triggers(engine)

    assert_integrity_ready(engine)

    db = SessionLocal()
    try:
        integrity_result = verify_chain(db)
        record_verification(db, integrity_result)
    finally:
        db.close()
    if not integrity_result.valid:
        reason = (
            f"{integrity_result.reason} (event position "
            f"{integrity_result.first_invalid_position})"
        )
        mark_integrity_failure(reason)
        raise RuntimeError(
            "Clinical event chain verification failed at startup: " + reason
        )
    clear_integrity_failure()

    if settings.AUTO_SEED:
        seed_hospital_data()

    if settings.INTEGRITY_CHECK_INTERVAL_SECONDS > 0:
        _integrity_task = asyncio.create_task(
            _integrity_loop(settings.INTEGRITY_CHECK_INTERVAL_SECONDS)
        )


@app.on_event("shutdown")
async def shutdown_event():
    global _integrity_task
    if _integrity_task is not None:
        _integrity_task.cancel()
        try:
            await _integrity_task
        except asyncio.CancelledError:
            pass
        _integrity_task = None


@app.get("/")
def root():
    return {
        "status": "online",
        "system": "Vigil Clinical Event Verification",
        "version": settings.VERSION,
        "phase": 1,
        "docs_url": "/docs"
    }
