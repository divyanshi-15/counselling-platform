from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models import User, UserRole

pwd_context = PasswordHasher()
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password_hash, password)
    except Exception:
        return False


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": getattr(role, "value", role),
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication") from exc


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> User:
    token = request.cookies.get("access_token")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> User | None:
    token = request.cookies.get("access_token")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        return None
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: UserRole | str):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        normalized = {getattr(role, "value", role) for role in roles}
        if getattr(user.role, "value", user.role) not in normalized:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user

    return dependency


def can_access_client_data(user: User, target_user_id: int) -> bool:
    if user.role == "admin":
        return True
    if user.role == "client":
        return user.id == target_user_id
    return False


def can_access_therapist_data(user: User, therapist_user_id: int) -> bool:
    if user.role == "admin":
        return True
    if user.role == "therapist":
        return user.id == therapist_user_id
    return False


def can_access_practice_owner_data(user: User, owner_user_id: int) -> bool:
    if user.role == "admin":
        return True
    if user.role == "practice_owner":
        return user.id == owner_user_id
    return False
