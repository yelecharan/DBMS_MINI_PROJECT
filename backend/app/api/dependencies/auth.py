from fastapi import Depends, HTTPException, status, Header, Cookie
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database.session import activate_database_role, get_db
from app.models.models import User
from app.core.security import decode_access_token
from app.core.config import settings

def get_current_user(
    access_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Extract authenticated user from HttpOnly cookie or Authorization Bearer header."""
    token = access_token
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided or session expired."
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token."
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated."
        )
    try:
        activate_database_role(db, user.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role is not authorized for database access."
        ) from exc
    return user


def require_role(allowed_roles: List[str]):
    """Authorization dependency factory verifying user has at least one of the allowed roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {allowed_roles}. User role: {current_user.role}"
            )
        return current_user
    return role_checker


def verify_detector_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify external detection pipeline API key (YOLOv8 + ByteTrack)."""
    if not x_api_key or x_api_key != settings.DETECTOR_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing detector API ingestion key (X-API-Key)."
        )
    return True
