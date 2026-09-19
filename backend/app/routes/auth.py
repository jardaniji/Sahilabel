from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth import DEMO_USERS, create_access_token, get_current_user, require_roles

router = APIRouter(tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = DEMO_USERS.get(form_data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    from app.auth import pwd_context
    if not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token(form_data.username, user["role"])
    return TokenResponse(access_token=token, role=user["role"])


@router.get("/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"username": user["username"], "role": user["role"], "authenticated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/auth/role-check")
def role_check(user: dict[str, Any] = Depends(require_roles("admin", "inspector"))) -> dict[str, Any]:
    return {"status": "ok", "username": user["username"], "role": user["role"]}
