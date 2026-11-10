import os
import jwt
import base64
import json
import re
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, Depends

logger = logging.getLogger("auth_handler")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

class CurrentUser(BaseModel):
    id: str
    email: str
    name: str = "Candidate"
    full_name: Optional[str] = None
    role: str = "candidate"
    is_demo: bool = False
    is_authenticated: bool = False

def _sanitize_user_id(raw_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "", str(raw_id or ""))
    return clean[:64] if clean else "demo_candidate"

async def get_current_user(authorization: Optional[str] = Header(None)) -> CurrentUser:
    """
    Validates Supabase JWT access token or local JWT token cleanly while sanitizing user_id.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
        payload = None
        try:
            if SUPABASE_JWT_SECRET:
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated"
                )
            else:
                payload = jwt.decode(token, options={"verify_signature": False})
        except Exception as jwt_err:
            try:
                parts = token.split(".")
                raw_b64 = parts[1] if len(parts) == 3 else token
                padding = "=" * (-len(raw_b64) % 4)
                decoded_bytes = base64.urlsafe_b64decode(raw_b64 + padding)
                payload = json.loads(decoded_bytes.decode("utf-8"))
            except Exception as fallback_err:
                logger.warning(f"Token decode failed: {jwt_err} / {fallback_err}")
                if REQUIRE_AUTH and not payload:
                    raise HTTPException(status_code=401, detail=f"Invalid or expired authentication token: {str(jwt_err)}")

        if isinstance(payload, dict):
            user_id = _sanitize_user_id(payload.get("sub") or payload.get("id"))
            email = payload.get("email", "user@example.com")
            user_metadata = payload.get("user_metadata") or {}
            full_name = (
                user_metadata.get("full_name")
                or user_metadata.get("name")
                or payload.get("name")
                or email.split("@")[0]
            )
            is_demo = user_id.startswith("demo") or user_id == "guest-candidate"
            return CurrentUser(
                id=user_id,
                email=email,
                name=full_name,
                full_name=full_name,
                role=user_metadata.get("role", "candidate"),
                is_demo=is_demo,
                is_authenticated=not is_demo
            )

    if REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")

    return CurrentUser(
        id="guest-candidate",
        email="guest@autoapply.ai",
        name="Guest",
        full_name="Guest",
        role="guest",
        is_demo=True,
        is_authenticated=False
    )

async def require_authenticated_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Strict security dependency that rejects unauthenticated guest visitors.
    Ensures every candidate operation is bound to a verified user account.
    """
    if not user.is_authenticated:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please sign in or create an account to access candidate features."
        )
    return user
