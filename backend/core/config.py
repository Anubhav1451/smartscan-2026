import os
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))
load_dotenv(os.path.join(backend_dir, "..", ".env"))
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "SmartScan 2026"
    VERSION: str = "1.0.0"
    TAGLINE: str = "Scan. Pay. Walk Out."
    
    # Supabase credentials (must come from .env)
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str = ""
    
    # Schema name: explicitly app2026 for SmartScan 2026
    SCHEMA_NAME: str = "app2026"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://localhost:4173"
    PORT: int = 8000
    
    model_config = SettingsConfigDict(
        env_file=(os.path.join(backend_dir, ".env"), ".env"),
        extra="ignore"
    )
    
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

settings = Settings()
