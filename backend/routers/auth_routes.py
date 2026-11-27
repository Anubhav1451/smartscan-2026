from fastapi import APIRouter, Depends
from core.auth import get_current_user, UserProfile
from core.db import get_supabase
from models.schemas import UserProfileResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/me", response_model=UserProfileResponse)
def get_caller_profile(user: UserProfile = Depends(get_current_user)):
    """
    Returns authenticated caller's profile loaded server-side from app2026.profiles.
    Never trusts role or store passed by the client.
    """
    sb = get_supabase()
    store = None
    if user.store_id:
        store_res = sb.table("stores").select("id, name, code, area, address").eq("id", user.store_id).execute()
        if store_res.data:
            store = store_res.data[0]
            
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        store_id=user.store_id,
        store=store
    )
