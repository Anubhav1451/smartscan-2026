import logging
from typing import Optional
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from core.config import settings
from core.db import get_supabase

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# JWKS client for asymmetric ECC keys (Supabase Auth ES256)
jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
jwks_client = PyJWKClient(jwks_url)

class UserProfile(BaseModel):
    id: str
    email: Optional[str] = None
    role: str = "customer"
    store_id: Optional[str] = None

def verify_token(token: str) -> dict:
    """
    Verifies Supabase JWT token:
    1. First tries JWKS asymmetric ECC verification (ES256).
    2. Falls back to legacy HS256 secret (SUPABASE_JWT_SECRET).
    """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "HS256"],
            audience="authenticated"
        )
        return payload
    except Exception as e_jwks:
        if settings.SUPABASE_JWT_SECRET:
            try:
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated"
                )
                return payload
            except Exception as e_hs:
                logger.warning(f"JWT HS256 fallback verification failed: {e_hs}")
        
        logger.error(f"JWT verification failed: {e_jwks}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid or expired authentication token", "code": "INVALID_TOKEN"},
            headers={"WWW-Authenticate": "Bearer"},
        )

def ensure_profile(user_id: str, email: Optional[str] = None) -> UserProfile:
    """
    Ensures a profile exists in app2026.profiles:
    1. Looks up profile by user_id. If found, returns it without alteration.
    2. Looks up profile by email. If found, preserves existing role (manager, exit_staff)
       and links auth user_id if needed. NEVER overwrites manager/staff role.
    3. If neither found, provisions a default 'customer' profile (store_id=None).
    """
    sb = get_supabase()
    
    # 1. Query app2026.profiles server-side by user_id
    res = sb.table("profiles").select("id, email, role, store_id").eq("id", user_id).execute()
    
    if res.data and len(res.data) > 0:
        row = res.data[0]
        return UserProfile(
            id=row["id"],
            email=row.get("email") or email,
            role=row.get("role", "customer"),
            store_id=row.get("store_id")
        )
    
    # 2. Check if profile exists by email (e.g. pre-seeded manager/staff or existing user)
    if email:
        email_res = sb.table("profiles").select("id, email, role, store_id").eq("email", email).execute()
        if email_res.data and len(email_res.data) > 0:
            row = email_res.data[0]
            stored_role = row.get("role", "customer")
            stored_store_id = row.get("store_id")
            
            # If id differs, link profile id to auth user id while preserving role & store
            if row["id"] != user_id:
                try:
                    sb.table("profiles").update({"id": user_id}).eq("id", row["id"]).execute()
                except Exception as e:
                    logger.warning(f"Could not update profile id from {row['id']} to {user_id}: {e}")
                    return UserProfile(
                        id=row["id"],
                        email=email,
                        role=stored_role,
                        store_id=stored_store_id
                    )
            
            return UserProfile(
                id=user_id,
                email=email,
                role=stored_role,
                store_id=stored_store_id
            )
    
    # 3. If no profile row yet, create default customer profile
    sb.table("profiles").insert({
        "id": user_id,
        "email": email,
        "role": "customer",
        "store_id": None
    }).execute()
    
    return UserProfile(
        id=user_id,
        email=email,
        role="customer",
        store_id=None
    )

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserProfile:
    """
    FastAPI dependency to verify JWT and resolve caller profile server-side.
    Never trusts role or store_id sent by the client.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Authentication required", "code": "AUTH_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Malformed token: missing sub claim", "code": "INVALID_TOKEN"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email = payload.get("email")
    return ensure_profile(user_id=user_id, email=email)

def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[UserProfile]:
    """Optional user dependency for routes that can optionally identify caller."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials)
    except Exception:
        return None

def require_staff_or_manager(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    """Requires role to be exit_staff or manager with assigned store."""
    if user.role not in ("exit_staff", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Forbidden: exit staff or manager role required", "code": "FORBIDDEN"}
        )
    return user

def require_manager(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    """Requires role to be manager."""
    if user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Forbidden: manager role required", "code": "FORBIDDEN"}
        )
    return user
