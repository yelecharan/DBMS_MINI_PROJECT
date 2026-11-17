from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models.models import User
from app.schemas.schemas import UserResponse, UserCreate
from app.api.dependencies.auth import require_role
from app.core.security import hash_password
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/users", tags=["User Administration"])

@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    """List application user accounts (Admin only)."""
    return db.query(User).order_by(User.created_at.desc()).all()

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    """Create new application user account and assign RBAC role (Admin only)."""
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    if user_in.role not in ["ADMIN", "SECURITY_OFFICER", "AUDITOR"]:
        raise HTTPException(status_code=400, detail="Invalid role specified.")

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email.lower(),
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_event(
        db=db,
        entity_type="USER",
        entity_id=new_user.id,
        action="CREATE",
        actor_user_id=admin.id,
        new_values={"email": new_user.email, "role": new_user.role, "full_name": new_user.full_name}
    )
    return new_user
