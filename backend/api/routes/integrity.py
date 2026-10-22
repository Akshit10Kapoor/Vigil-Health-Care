from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.middleware.access_control import require_roles
from backend.event_store.database import get_db
from backend.event_store.integrity import (
    clear_integrity_failure,
    mark_integrity_failure,
    record_verification,
    verify_chain,
)
from backend.event_store.models import StaffModel

router = APIRouter(prefix="/integrity", tags=["Integrity Verification"])

INTEGRITY_ROLES = ["admin", "quality_team"]


@router.get("/chain")
def get_chain_status(
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(require_roles(INTEGRITY_ROLES)),
):
    result = verify_chain(db)
    if result.valid:
        clear_integrity_failure()
    else:
        mark_integrity_failure(result.reason or "chain verification failed")
    return result.as_dict()


@router.post("/chain/verify")
def run_chain_verification(
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(require_roles(INTEGRITY_ROLES)),
):
    result = verify_chain(db)
    record_verification(db, result)
    if result.valid:
        clear_integrity_failure()
    else:
        mark_integrity_failure(result.reason or "chain verification failed")
    return result.as_dict()
