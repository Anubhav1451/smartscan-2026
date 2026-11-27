from typing import Optional
from supabase import create_client, Client, ClientOptions
from core.config import settings

_supabase_client: Optional[Client] = None
_supabase_auth_client: Optional[Client] = None

def get_supabase() -> Client:
    """
    Returns the Supabase service-role client explicitly configured
    with the 'app2026' schema for all database table operations.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            options=ClientOptions(schema=settings.SCHEMA_NAME)
        )
    return _supabase_client

def get_auth_client() -> Client:
    """
    Returns a client for Auth admin operations (auth does not require schema).
    """
    global _supabase_auth_client
    if _supabase_auth_client is None:
        _supabase_auth_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _supabase_auth_client
