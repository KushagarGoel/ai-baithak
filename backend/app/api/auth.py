"""Authentication routes for Agent Council."""

from fastapi import APIRouter, Response, Request, HTTPException, status, Depends

from app.core.auth import (
    hash_password, verify_password, generate_user_id,
    create_session_token, generate_csrf_token
)
from app.core.database import db
from app.core.config import settings
from app.models.schemas import UserCreate, UserLogin, UserResponse, UserRole
from app.api.deps import get_current_user, optional_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, response: Response):
    """Register a new user."""
    # Check if email exists
    if db.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username exists
    if db.get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # First user becomes admin
    role = UserRole.ADMIN if not db.list_users() else UserRole.USER

    # Hash password and create user
    user_id = generate_user_id()
    password_hash = hash_password(user_data.password)

    user = db.create_user(
        user_id=user_id,
        email=user_data.email,
        username=user_data.username,
        password_hash=password_hash,
        role=role
    )

    # Set session cookie
    session_token = create_session_token(user_id)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE
    )

    # Set CSRF cookie
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE
    )

    return UserResponse(**user)


@router.post("/login")
async def login(credentials: UserLogin, response: Response):
    """Login a user."""
    # Try to find user by username or email
    user = db.get_user_by_username(credentials.username)
    if not user:
        user = db.get_user_by_email(credentials.username)

    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Set session cookie
    session_token = create_session_token(user["id"])
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE
    )

    # Set CSRF cookie
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE
    )

    return {
        "message": "Login successful",
        "user": UserResponse(**user)
    }


@router.post("/logout")
async def logout(response: Response):
    """Logout a user."""
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)
    return {"message": "Logout successful"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info."""
    return current_user


@router.get("/csrf")
async def get_csrf(response: Response):
    """Get a CSRF token."""
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE
    )
    return {"csrf_token": csrf_token}
