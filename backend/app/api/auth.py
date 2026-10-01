from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import DEMO_USERS, create_token, current_user, password_is_demo_default, seed_password, verify_password
from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas import DemoAccountOut, LoginIn, LoginOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

BAD_LOGIN = "Invalid username or password."


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.get(User, payload.username.strip().lower())
    # Same message whether the user or the password is wrong.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail=BAD_LOGIN)
    token, exp = create_token(user.username)
    return LoginOut(token=token, expires_at=exp, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.get("/demo-accounts", response_model=list[DemoAccountOut])
def demo_accounts():
    """Demo logins for the login page, only when DEMO_MODE is on. A password
    is shown only while it is still the published demo default."""
    if not settings.demo_mode:
        return []
    return [
        DemoAccountOut(
            username=u.username,
            full_name=u.full_name,
            designation=u.designation,
            role=u.role,
            demo_password=seed_password(u) if password_is_demo_default(u) else None,
        )
        for u in DEMO_USERS
    ]
