from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.event_store.database import get_db
from backend.event_store.models import StaffModel, WardModel
from backend.api.middleware.access_control import (
    verify_password, get_password_hash, create_access_token, get_current_staff
)

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    staff_id: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff_id: str
    role: str
    full_name: str
    assigned_ward_id: Optional[str] = None

class StaffCreateRequest(BaseModel):
    staff_id: str
    full_name: str
    role: str # nurse, ward_manager, quality_team, admin
    password: str
    assigned_ward_id: Optional[str] = None

class StaffResponse(BaseModel):
    staff_id: str
    full_name: str
    role: str
    assigned_ward_id: Optional[str] = None

@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    staff = db.query(StaffModel).filter(StaffModel.staff_id == login_data.staff_id).first()
    if not staff or not verify_password(login_data.password, staff.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect staff ID or password"
        )
    if not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff account is inactive"
        )

    access_token = create_access_token(data={"sub": staff.staff_id, "role": staff.role})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        staff_id=staff.staff_id,
        role=staff.role,
        full_name=staff.full_name,
        assigned_ward_id=staff.assigned_ward_id
    )

@router.get("/me", response_model=StaffResponse)
def get_me(current_staff: StaffModel = Depends(get_current_staff)):
    return StaffResponse(
        staff_id=current_staff.staff_id,
        full_name=current_staff.full_name,
        role=current_staff.role,
        assigned_ward_id=current_staff.assigned_ward_id
    )

@router.post("/staff", response_model=StaffResponse)
def create_staff(
    staff_data: StaffCreateRequest,
    db: Session = Depends(get_db),
    current_staff: StaffModel = Depends(get_current_staff)
):
    if current_staff.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create staff accounts")
    
    existing = db.query(StaffModel).filter(StaffModel.staff_id == staff_data.staff_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Staff ID already exists")

    hashed_pw = get_password_hash(staff_data.password)
    new_staff = StaffModel(
        staff_id=staff_data.staff_id,
        full_name=staff_data.full_name,
        role=staff_data.role,
        hashed_password=hashed_pw,
        assigned_ward_id=staff_data.assigned_ward_id
    )
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)

    return StaffResponse(
        staff_id=new_staff.staff_id,
        full_name=new_staff.full_name,
        role=new_staff.role,
        assigned_ward_id=new_staff.assigned_ward_id
    )
