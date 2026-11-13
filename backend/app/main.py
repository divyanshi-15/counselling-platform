from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.app.db import Base, engine, get_db
from backend.app.models import User
from backend.app.schemas import MessageResponse, UserCreate, UserLogin, UserOut
from backend.app.safety import render_prompt_data, risk_check, validate_ai_output

app = FastAPI(title="Counselling Practice Platform")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "Hello from Caddy"}


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


@app.post("/auth/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="User already exists")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        language=payload.language,
        name=payload.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login")
def login(payload: UserLogin, db: Session = Depends(get_db)) -> JSONResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.email, user.role)
    response = JSONResponse({"message": "Logged in", "user": UserOut.model_validate(user).model_dump()})
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@app.post("/demo/safety-check")
def demo_safety_check(text: str) -> dict[str, object]:
    result = risk_check(text)
    return {
        "flagged": result["flagged"],
        "message": result["message"],
        "blocked": result["blocked"],
    }


@app.post("/demo/prompt-guard")
def demo_prompt_guard(text: str) -> dict[str, str]:
    safe_text = render_prompt_data(text)
    return {"sanitized": safe_text}


@app.post("/demo/ai-output-validator")
def demo_ai_output_validator(text: str) -> MessageResponse:
    valid, reason = validate_ai_output(text)
    if not valid:
        raise HTTPException(status_code=422, detail=reason)
    return MessageResponse(message="Approved")
