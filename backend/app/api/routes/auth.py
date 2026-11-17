from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.database.session import activate_database_role, get_db
from app.models.models import User
from app.schemas.schemas import LoginRequest, TokenResponse, UserResponse
from app.core.security import verify_password, create_access_token
from app.api.dependencies.auth import get_current_user
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate user credentials and issue JWT in HttpOnly cookie and JSON body."""
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled."
        )

    activate_database_role(db, user.role)
    token = create_access_token(subject=user.id, role=user.role)

    # Set secure HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False, # Set True in production HTTPS
        max_age=8 * 3600
    )

    log_audit_event(
        db=db,
        entity_type="USER",
        entity_id=user.id,
        action="LOGIN",
        actor_user_id=user.id,
        new_values={"email": user.email, "role": user.role}
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        full_name=user.full_name,
        email=user.email
    )

@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Clear HttpOnly authentication cookie."""
    response.delete_cookie(key="access_token")
    log_audit_event(
        db=db,
        entity_type="USER",
        entity_id=current_user.id,
        action="LOGOUT",
        actor_user_id=current_user.id
    )
    return {"message": "Successfully logged out."}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated session identity."""
    return current_user
