from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import DEMO_USERS, create_access_token, get_current_user, require_roles

router = APIRouter(tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/auth/login", response_model=TokenResponse)
def login(username: str, password: str):
    user = DEMO_USERS.get(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user.get("hashed_password"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    from app.auth import pwd_context
    if not pwd_context.verify(password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    token = create_access_token(username, user["role"])
    return TokenResponse(access_token=token, role=user["role"])


@router.get("/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"username": user["username"], "role": user["role"], "authenticated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/auth/role-check")
def role_check(user: dict[str, Any] = Depends(require_roles("admin", "inspector"))) -> dict[str, Any]:
    return {"status": "ok", "username": user["username"], "role": user["role"]}
