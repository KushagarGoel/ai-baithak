"""API dependencies for authentication."""

from typing import Optional

from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer

from app.core.auth import decode_session_token
from app.core.database import db
from app.models.schemas import User, UserRole

security = HTTPBearer(auto_error=False)


async def get_current_user(request: Request) -> User:
    """Get current user from session cookie."""
    session_token = request.cookies.get("session_id")

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    session_data = decode_session_token(session_token)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )

    user = db.get_user_by_id(session_data["user_id"])
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return User(**user)


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verify current user is an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def optional_current_user(request: Request) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
