"""Authentication utilities for Agent Council."""

import uuid
import secrets
from datetime import datetime
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import URLSafeSerializer, BadSignature

from app.core.config import settings

# Password hashing using Argon2 (modern, secure, no 72-byte limit)
ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)

# Session serializer for signed cookies
serializer = URLSafeSerializer(settings.SECRET_KEY, salt="session")


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False


def generate_user_id() -> str:
    """Generate a unique user ID."""
    return f"user_{uuid.uuid4().hex[:12]}"


def create_session_token(user_id: str) -> str:
    """Create a signed session token."""
    return serializer.dumps({"user_id": user_id, "created_at": datetime.utcnow().isoformat()})


def decode_session_token(token: str) -> Optional[dict]:
    """Decode and verify a session token."""
    try:
        return serializer.loads(token)
    except BadSignature:
        return None


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)
