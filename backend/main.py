import logging
import os
import sys
from typing import Optional

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.rate_limit import global_rate_limiter
from core.auth import get_current_user, get_optional_user, UserProfile
from routers import stores, scan, orders, exit, staff, manager, auth_routes
from routers.manager import get_manager_store_dashboard, reset_demo_data

logger = logging.getLogger("smartscan")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="SmartScan 2026 API — Multi-Retailer Scan-and-Go Checkout System"
)

# Rule 8: Hardening — Sliding-window global rate limiting per IP
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not request.url.path.startswith(("/health", "/docs", "/openapi.json")):
        global_rate_limiter.check(request)
    return await call_next(request)

# Rule: Error Hygiene — Clean responses only, never leak stack traces, SQL, or internal details
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    content = {"detail": exc.detail} if isinstance(exc.detail, (dict, list)) else {"detail": {"error": str(exc.detail), "code": "HTTP_ERROR"}}
    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = "; ".join([f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": {"error": error_msg, "code": "VALIDATION_ERROR"}}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": {"error": "An unexpected server error occurred. Please try again.", "code": "INTERNAL_SERVER_ERROR"}}
    )

# Rule: CORS allows only our own frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_routes.router)
app.include_router(stores.router)
app.include_router(scan.router)
app.include_router(orders.router)
app.include_router(exit.router)
app.include_router(staff.router)
app.include_router(manager.router)

# Aliases for frontend backward compatibility
@app.get("/dashboard/summary", tags=["Dashboard"])
def get_dashboard_summary_alias(
    store_id: Optional[str] = None,
    date_range: str = "today",
    user: Optional[UserProfile] = Depends(get_current_user)
):
    if not store_id and user and user.store_id:
        store_id = user.store_id
    if not store_id:
        from core.db import get_supabase
        sb = get_supabase()
        first_store = sb.table("stores").select("id").limit(1).execute()
        if first_store.data:
            store_id = first_store.data[0]["id"]
        else:
            raise HTTPException(status_code=404, detail="No store found")
    return get_manager_store_dashboard(store_id=store_id, date_range=date_range, user=user)

@app.post("/dashboard/reset-demo", tags=["Dashboard"])
def reset_demo_alias(user: Optional[UserProfile] = Depends(get_optional_user)):
    return reset_demo_data(user=user)

@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "tagline": settings.TAGLINE,
        "schema": settings.SCHEMA_NAME
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
