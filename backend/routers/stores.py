from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Request, Response
from core.db import get_supabase
from core.auth import get_current_user, UserProfile
from models.schemas import (
    StoreResponse, 
    ProductResponse, 
    ProductCreateRequest, 
    ProductUpdateRequest,
    ImportPreviewResponse,
    ImportExecuteResponse,
    UnknownScanResponse
)
from routers.manager import (
    add_store_product,
    update_store_product,
    manager_barcode_lookup,
    get_next_internal_barcode,
    download_import_template,
    preview_csv_import,
    execute_csv_import,
    get_store_unknown_scans,
    dismiss_unknown_scan
)

router = APIRouter(tags=["Stores"])

@router.get("/stores", response_model=List[StoreResponse])
def list_stores():
    """List all active stores from app2026 schema."""
    sb = get_supabase()
    res = sb.table("stores").select("id, retailer_id, name, code, area, address, is_active").eq("is_active", True).order("name").execute()
    return res.data or []

@router.get("/stores/{store_id}/products", response_model=List[ProductResponse])
def list_store_products(
    store_id: str,
    search: Optional[str] = Query(None, description="Search by name or barcode")
):
    """List products for a specific store with search support."""
    sb = get_supabase()
    query = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit, gst_rate").eq("store_id", store_id)
    if search and search.strip():
        s = search.strip()
        query = query.or_(f"name.ilike.%{s}%,barcode.ilike.%{s}%,category.ilike.%{s}%")
    res = query.order("name").execute()
    return res.data or []

# Aliases for frontend backward compatibility
@router.get("/stores/{store_id}/products/barcode-lookup")
def manager_barcode_lookup_alias(store_id: str, barcode: str = Query(...), user: Optional[UserProfile] = Depends(get_current_user)):
    return manager_barcode_lookup(store_id=store_id, barcode=barcode, user=user)

@router.get("/stores/{store_id}/next-internal-barcode")
def get_next_internal_barcode_alias(store_id: str, user: Optional[UserProfile] = Depends(get_current_user)):
    return get_next_internal_barcode(store_id=store_id, user=user)

@router.post("/stores/{store_id}/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def add_store_product_alias(store_id: str, req: ProductCreateRequest, user: UserProfile = Depends(get_current_user)):
    return add_store_product(store_id=store_id, req=req, user=user)

@router.patch("/stores/{store_id}/products/{product_id}", response_model=ProductResponse)
def update_store_product_alias(store_id: str, product_id: str, req: ProductUpdateRequest, user: UserProfile = Depends(get_current_user)):
    return update_store_product(store_id=store_id, product_id=product_id, req=req, user=user)

@router.get("/stores/{store_id}/products/import-template")
def download_import_template_alias(store_id: str, user: Optional[UserProfile] = Depends(get_current_user)):
    return download_import_template(store_id=store_id, user=user)

@router.post("/stores/{store_id}/products/import-preview", response_model=ImportPreviewResponse)
async def preview_csv_import_alias(store_id: str, request: Request, file: Optional[UploadFile] = File(None), user: Optional[UserProfile] = Depends(get_current_user)):
    return await preview_csv_import(store_id=store_id, request=request, file=file, user=user)

@router.post("/stores/{store_id}/products/import", response_model=ImportExecuteResponse)
async def execute_csv_import_alias(store_id: str, request: Request, file: Optional[UploadFile] = File(None), user: Optional[UserProfile] = Depends(get_current_user)):
    return await execute_csv_import(store_id=store_id, request=request, file=file, user=user)

@router.get("/stores/{store_id}/unknown-scans", response_model=List[UnknownScanResponse])
def get_store_unknown_scans_alias(store_id: str, user: Optional[UserProfile] = Depends(get_current_user)):
    return get_store_unknown_scans(store_id=store_id, user=user)

@router.delete("/stores/{store_id}/unknown-scans/{scan_id_or_barcode}")
def dismiss_unknown_scan_alias(store_id: str, scan_id_or_barcode: str, user: Optional[UserProfile] = Depends(get_current_user)):
    return dismiss_unknown_scan(store_id=store_id, scan_id_or_barcode=scan_id_or_barcode, user=user)

