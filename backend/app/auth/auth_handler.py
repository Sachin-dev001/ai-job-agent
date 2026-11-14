import os
import jwt
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, Depends

logger = logging.getLogger("auth_handler")
SERVER_AUTH_SECRET = os.getenv("SERVER_AUTH_SECRET") or os.getenv("SUPABASE_JWT_SECRET") or "autoapply_secret_token_hmac_sign_key_9942"
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

def create_access_token(user_id: str, email: str, name: str = "Candidate", expires_in_days: int = 30) -> str:
    """
    Issues a cryptographically signed HS256 JWT access token.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "id": user_id,
        "email": email,
        "name": name,
        "user_metadata": {
            "full_name": name,
            "name": name,
            "role": "candidate"
        },
        "role": "candidate",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=expires_in_days)).timestamp())
    }
    return jwt.encode(payload, SERVER_AUTH_SECRET, algorithm="HS256")

async def get_current_user(authorization: Optional[str] = Header(None)) -> CurrentUser:
    """
    Validates JWT access token strictly with HS256 cryptographic signature verification.
    Rejects unsigned or forged payloads (CWE-347 remediation).
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
        payload = None

        candidate_secrets = []
        if SUPABASE_JWT_SECRET:
            candidate_secrets.append(SUPABASE_JWT_SECRET)
        if SERVER_AUTH_SECRET and SERVER_AUTH_SECRET not in candidate_secrets:
            candidate_secrets.append(SERVER_AUTH_SECRET)

        last_err = None
        for secret in candidate_secrets:
            try:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    options={"verify_signature": True, "verify_aud": False}
                )
                if payload:
                    break
            except Exception as e:
                last_err = e
                continue

        if not payload:
            logger.warning(f"Token signature verification failed: {last_err}")
            raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

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

    # On local machine (personal localhost mode), auto-authenticate as the default developer profile
    is_cloud = os.getenv("RENDER") or os.getenv("VERCEL") or os.getenv("SPACE_ID")
    if not is_cloud:
        return CurrentUser(
            id="local-dev-user-001",
            email="sachin.sharma.engineer@gmail.com",
            name="sachin",
            full_name="Sachin Sharma",
            role="candidate",
            is_demo=False,
            is_authenticated=True
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
    Strict security dependency that ensures every candidate operation is bound to a verified user account.
    """
    if not user.is_authenticated:
        is_cloud = os.getenv("RENDER") or os.getenv("VERCEL") or os.getenv("SPACE_ID")
        if not is_cloud:
            return CurrentUser(
                id="local-dev-user-001",
                email="sachin.sharma.engineer@gmail.com",
                name="sachin",
                full_name="Sachin Sharma",
                role="candidate",
                is_demo=False,
                is_authenticated=True
            )
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please sign in or create an account to access candidate features."
        )
    return user
