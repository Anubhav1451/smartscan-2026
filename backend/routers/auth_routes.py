from fastapi import APIRouter, Depends
from core.auth import get_current_user, ensure_profile, UserProfile
from core.db import get_supabase
from models.schemas import UserProfileResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

def resolve_user_store(sb, store_id):
    if not store_id:
        return None
    store_res = sb.table("stores").select("id, name, code, area, address").eq("id", store_id).execute()
    return store_res.data[0] if store_res.data else None

@router.get("/me", response_model=UserProfileResponse)
def get_caller_profile(user: UserProfile = Depends(get_current_user)):
    """
    Returns authenticated caller's profile loaded server-side from app2026.profiles.
    Never trusts role or store passed by the client.
    """
    sb = get_supabase()
    store = resolve_user_store(sb, user.store_id)
            
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        store_id=user.store_id,
        store=store
    )

@router.post("/bootstrap", response_model=UserProfileResponse)
def bootstrap_caller_profile(user: UserProfile = Depends(get_current_user)):
    """
    Bootstraps the caller's profile in app2026.profiles.
    Ensures a row exists (id = auth user id, email, role='customer', store_id=None).
    Existing users (e.g. manager/staff by email match) keep their stored role - never overwritten.
    Returns the resolved profile.
    """
    profile = ensure_profile(user_id=user.id, email=user.email)
    sb = get_supabase()
    store = resolve_user_store(sb, profile.store_id)
            
    return UserProfileResponse(
        id=profile.id,
        email=profile.email,
        role=profile.role,
        store_id=profile.store_id,
        store=store
    )
