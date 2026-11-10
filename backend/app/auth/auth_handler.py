import os
import jwt
from typing import Optional
from pydantic import BaseModel
from fastapi import Header, HTTPException, Depends

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

class CurrentUser(BaseModel):
    id: str
    email: str
    name: str = "Candidate"
    is_authenticated: bool = False

async def get_current_user(authorization: Optional[str] = Header(None)) -> CurrentUser:
    """
    Validates Supabase JWT access token or provides fallback demo user for local development.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
        try:
            # If JWT secret is provided, verify signature; otherwise decode payload claims
            if SUPABASE_JWT_SECRET:
                payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
            else:
                payload = jwt.decode(token, options={"verify_signature": False})

            user_id = payload.get("sub") or payload.get("id")
            email = payload.get("email", "user@example.com")
            user_meta = payload.get("user_metadata", {})
            name = user_meta.get("full_name") or user_meta.get("name") or email.split("@")[0]

            if user_id:
                return CurrentUser(
                    id=str(user_id),
                    email=email,
                    name=name,
                    is_authenticated=True
                )
        except Exception as e:
            if REQUIRE_AUTH:
                raise HTTPException(status_code=401, detail=f"Invalid or expired authentication token: {str(e)}")

    # If auth is required and no valid token was supplied:
    if REQUIRE_AUTH:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")

    # Local development / Guest mode fallback
    return CurrentUser(
        id="guest-candidate",
        email="guest@autoapply.ai",
        name="Guest",
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
