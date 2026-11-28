import io
import csv
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Request, Response

from core.db import get_supabase
from core.auth import get_current_user, get_optional_user, UserProfile, require_manager
from models.schemas import (
    ProductResponse,
    ProductCreateRequest,
    ProductUpdateRequest,
    ImportPreviewResponse,
    ImportExecuteResponse,
    ImportRowError,
    UnknownScanResponse,
    ResetDemoResponse
)
import seed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manager", tags=["Manager"])

def verify_manager_store_access(user: Optional[UserProfile], store_id: str):
    """Enforces manager store isolation: a manager cannot manage another store."""
    if not user:
        return
    if user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Access forbidden: manager role required", "code": "FORBIDDEN"}
        )
    if user.store_id and str(user.store_id) != str(store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Access forbidden: you can only manage your assigned store", "code": "STORE_ISOLATION_FORBIDDEN"}
        )

# --------------------------------------------------------------------------
# 1. Product Listing & Search & Barcode Lookup
# --------------------------------------------------------------------------
@router.get("/stores/{store_id}/products", response_model=List[ProductResponse])
def get_manager_store_products(
    store_id: str,
    search: Optional[str] = Query(None, description="Search by product name or barcode"),
    user: UserProfile = Depends(get_current_user)
):
    """Retrieve store catalogue with search support and manager isolation check."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    query = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", store_id)
    
    if search and search.strip():
        s = search.strip()
        query = query.or_(f"name.ilike.%{s}%,barcode.ilike.%{s}%,category.ilike.%{s}%")
        
    res = query.order("name").execute()
    return res.data or []

@router.get("/stores/{store_id}/products/barcode-lookup")
def manager_barcode_lookup(
    store_id: str,
    barcode: str = Query(..., description="Barcode to lookup"),
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """
    Checks if a barcode exists in the current store, in another store, or is brand new.
    Used by Manager Add Product modal to auto-populate existing metadata.
    """
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    clean_barcode = barcode.strip()
    
    # 1. Check current store
    cur = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", store_id).eq("barcode", clean_barcode).execute()
    if cur.data and len(cur.data) > 0:
        return {
            "status": "EXISTS_CURRENT_STORE",
            "product": cur.data[0]
        }
        
    # 2. Check other stores
    other = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").neq("store_id", store_id).eq("barcode", clean_barcode).limit(1).execute()
    if other.data and len(other.data) > 0:
        return {
            "status": "EXISTS_OTHER_STORE",
            "other_product": other.data[0]
        }
        
    return {
        "status": "NEW_PRODUCT"
    }

@router.get("/stores/{store_id}/next-internal-barcode")
def get_next_internal_barcode(
    store_id: str,
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """Generates a store-internal barcode starting with SS."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    import random
    for _ in range(20):
        code = f"SS{random.randint(10000, 99999)}"
        exists = sb.table("products").select("id").eq("barcode", code).execute()
        if not exists.data:
            return {"barcode": code}
    return {"barcode": f"SS{random.randint(10000, 99999)}"}

# --------------------------------------------------------------------------
# 2. Scan-to-Add: Create New Product
# --------------------------------------------------------------------------
@router.post("/stores/{store_id}/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def add_store_product(
    store_id: str,
    req: ProductCreateRequest,
    user: UserProfile = Depends(get_current_user)
):
    """
    Manager scans barcode and fills details -> product is live instantly.
    Duplicate (store_id, barcode) returns 409 Conflict.
    On save, removes barcode from unknown-scans queue if present.
    """
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    
    # 1. Check if store exists
    store_check = sb.table("stores").select("id").eq("id", store_id).execute()
    if not store_check.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Store not found", "code": "STORE_NOT_FOUND"}
        )
        
    barcode = req.barcode.strip()
    name = req.name.strip()
    if not barcode or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Barcode and name are required", "code": "VALIDATION_ERROR"}
        )
        
    # 2. Check for duplicate within this store
    dup_res = sb.table("products").select("id").eq("store_id", store_id).eq("barcode", barcode).execute()
    if dup_res.data and len(dup_res.data) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": f"Product with barcode '{barcode}' already exists in this store", "code": "DUPLICATE_PRODUCT"}
        )
        
    # 3. Insert product
    insert_data = {
        "store_id": store_id,
        "barcode": barcode,
        "name": name,
        "brand": req.brand.strip() if req.brand else None,
        "category": req.category.strip() if req.category else "General",
        "price": req.price,
        "mrp": req.mrp if req.mrp is not None else req.price,
        "stock": req.stock,
        "unit": req.unit.strip() if req.unit else "1 pc",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    ins_res = sb.table("products").insert(insert_data).execute()
    if not ins_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to create product in database", "code": "DB_ERROR"}
        )
    created_product = ins_res.data[0]
    
    # 4. Remove barcode from unknown_scans if present
    try:
        sb.table("unknown_scans").delete().eq("store_id", store_id).eq("barcode", barcode).execute()
    except Exception:
        pass
        
    return created_product

# --------------------------------------------------------------------------
# 3. Quick Edit: Patch Price, Stock, etc.
# --------------------------------------------------------------------------
@router.patch("/stores/{store_id}/products/{product_id}", response_model=ProductResponse)
def update_store_product(
    store_id: str,
    product_id: str,
    req: ProductUpdateRequest,
    user: UserProfile = Depends(get_current_user)
):
    """Inline edit of price, stock, and product details."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    
    # Verify product belongs to store
    prod_res = sb.table("products").select("id").eq("id", product_id).eq("store_id", store_id).execute()
    if not prod_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Product not found in this store", "code": "PRODUCT_NOT_FOUND"}
        )
        
    updates = {}
    if req.name is not None and req.name.strip():
        updates["name"] = req.name.strip()
    if req.brand is not None:
        updates["brand"] = req.brand.strip() if req.brand else None
    if req.category is not None and req.category.strip():
        updates["category"] = req.category.strip()
    if req.price is not None:
        if req.price < 0:
            raise HTTPException(status_code=400, detail={"error": "Price cannot be negative", "code": "VALIDATION_ERROR"})
        updates["price"] = int(req.price)
    if req.mrp is not None:
        updates["mrp"] = int(req.mrp)
    if req.stock is not None:
        if req.stock < 0:
            raise HTTPException(status_code=400, detail={"error": "Stock cannot be negative", "code": "VALIDATION_ERROR"})
        updates["stock"] = int(req.stock)
    if req.unit is not None:
        updates["unit"] = req.unit.strip() if req.unit else "1 pc"
        
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        up_res = sb.table("products").update(updates).eq("id", product_id).eq("store_id", store_id).execute()
        if up_res.data:
            return up_res.data[0]
            
    # Return existing if no updates
    cur = sb.table("products").select("*").eq("id", product_id).execute()
    return cur.data[0]

# --------------------------------------------------------------------------
# 4. CSV Bulk Import: Template, Preview & Execute
# --------------------------------------------------------------------------
@router.get("/stores/{store_id}/products/import-template")
def download_import_template(
    store_id: str,
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """Download standard CSV template for bulk product import."""
    verify_manager_store_access(user, store_id)
    csv_content = (
        "barcode,name,brand,category,price,mrp,stock,unit\n"
        "8901234567890,Sample Product,Sample Brand,General,199,249,20,1 pc\n"
        "8909876543210,Another Item,Brand X,Snacks,50,60,100,200g\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="smartscan_products_template.csv"'}
    )

def parse_and_validate_csv(csv_text: str, store_id: str) -> Dict[str, Any]:
    """Parses CSV text and validates each row."""
    reader = csv.DictReader(io.StringIO(csv_text))
    
    to_add = []
    to_update = []
    failed = []
    valid_candidates = []
    seen_barcodes = {}
    
    row_num = 1
    for r in reader:
        row_num += 1
        # Skip completely blank rows
        if not any(v.strip() for v in r.values() if v):
            continue
            
        barcode = (r.get("barcode") or "").strip()
        name = (r.get("name") or "").strip()
        brand = (r.get("brand") or "").strip() or None
        category = (r.get("category") or "").strip() or "General"
        price_str = (r.get("price") or "").strip()
        mrp_str = (r.get("mrp") or "").strip()
        stock_str = (r.get("stock") or "").strip()
        unit = (r.get("unit") or "").strip() or "1 pc"
        
        if not barcode:
            failed.append(ImportRowError(row=row_num, barcode="", name=name, reason="Missing barcode"))
            continue
            
        if not name:
            failed.append(ImportRowError(row=row_num, barcode=barcode, name="", reason="Missing product name"))
            continue
            
        # Price validation: must be whole number >= 0
        try:
            if "." in price_str:
                failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason=f"Price must be a valid whole number (INR), got '{price_str}'"))
                continue
            price = int(price_str)
            if price < 0:
                failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason="Price cannot be negative"))
                continue
        except (ValueError, TypeError):
            failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason=f"Price must be a valid whole number (INR), got '{price_str}'"))
            continue
            
        # Stock validation: must be whole number >= 0
        try:
            if "." in stock_str:
                failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason=f"Stock must be a valid whole number, got '{stock_str}'"))
                continue
            stock = int(stock_str)
            if stock < 0:
                failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason="Stock cannot be negative"))
                continue
        except (ValueError, TypeError):
            failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason=f"Stock must be a valid whole number, got '{stock_str}'"))
            continue
            
        mrp = None
        if mrp_str:
            try:
                mrp = int(mrp_str)
            except Exception:
                mrp = price
                
        # Duplicate within same file check
        if barcode in seen_barcodes:
            failed.append(ImportRowError(row=row_num, barcode=barcode, name=name, reason=f"Duplicate barcode in CSV (first seen at row {seen_barcodes[barcode]})"))
            continue
            
        seen_barcodes[barcode] = row_num
        valid_candidates.append({
            "row": row_num,
            "store_id": store_id,
            "barcode": barcode,
            "name": name,
            "brand": brand,
            "category": category,
            "price": price,
            "mrp": mrp or price,
            "stock": stock,
            "unit": unit
        })
        
    # Check DB for existing products in this store
    if valid_candidates:
        sb = get_supabase()
        candidate_barcodes = [c["barcode"] for c in valid_candidates]
        existing_res = sb.table("products").select("id, barcode, name, price, stock").eq("store_id", store_id).in_("barcode", candidate_barcodes).execute()
        existing_map = {p["barcode"]: p for p in (existing_res.data or [])}
        
        for c in valid_candidates:
            if c["barcode"] in existing_map:
                ex = existing_map[c["barcode"]]
                to_update.append({
                    "row": c["row"],
                    "id": ex["id"],
                    "barcode": c["barcode"],
                    "name": c["name"],
                    "brand": c["brand"],
                    "category": c["category"],
                    "new_price": c["price"],
                    "old_price": ex.get("price"),
                    "new_stock": c["stock"],
                    "old_stock": ex.get("stock"),
                    "mrp": c["mrp"],
                    "unit": c["unit"]
                })
            else:
                to_add.append({
                    "row": c["row"],
                    "barcode": c["barcode"],
                    "name": c["name"],
                    "brand": c["brand"],
                    "category": c["category"],
                    "price": c["price"],
                    "mrp": c["mrp"],
                    "stock": c["stock"],
                    "unit": c["unit"]
                })
                
    total_processed = len(to_add) + len(to_update) + len(failed)
    return {
        "total_rows": total_processed,
        "valid_count": len(to_add) + len(to_update),
        "to_add_count": len(to_add),
        "to_update_count": len(to_update),
        "to_fail_count": len(failed),
        "to_add": to_add,
        "to_update": to_update,
        "failed": failed,
        "valid_candidates": valid_candidates
    }

@router.post("/stores/{store_id}/products/import-preview", response_model=ImportPreviewResponse)
async def preview_csv_import(
    store_id: str,
    request: Request,
    file: Optional[UploadFile] = File(None),
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """Dry run only: validates rows, detects adds vs updates vs failures without saving."""
    verify_manager_store_access(user, store_id)
    
    if file:
        content = await file.read()
        csv_text = content.decode("utf-8", errors="replace")
    else:
        body = await request.body()
        csv_text = body.decode("utf-8", errors="replace")
        
    res = parse_and_validate_csv(csv_text, store_id)
    return ImportPreviewResponse(
        total_rows=res["total_rows"],
        valid_count=res["valid_count"],
        to_add_count=res["to_add_count"],
        to_update_count=res["to_update_count"],
        to_fail_count=res["to_fail_count"],
        to_add=res["to_add"],
        to_update=res["to_update"],
        failed=res["failed"]
    )

@router.post("/stores/{store_id}/products/import", response_model=ImportExecuteResponse)
async def execute_csv_import(
    store_id: str,
    request: Request,
    file: Optional[UploadFile] = File(None),
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """Applies CSV file as an upsert on (store_id, barcode)."""
    verify_manager_store_access(user, store_id)
    
    if file:
        content = await file.read()
        csv_text = content.decode("utf-8", errors="replace")
    else:
        body = await request.body()
        csv_text = body.decode("utf-8", errors="replace")
        
    parsed = parse_and_validate_csv(csv_text, store_id)
    candidates = parsed["valid_candidates"]
    sb = get_supabase()
    
    now_iso = datetime.now(timezone.utc).isoformat()
    upsert_rows = [
        {
            "store_id": store_id,
            "barcode": c["barcode"],
            "name": c["name"],
            "brand": c["brand"],
            "category": c["category"],
            "price": c["price"],
            "mrp": c["mrp"],
            "stock": c["stock"],
            "unit": c["unit"],
            "updated_at": now_iso
        }
        for c in candidates
    ]
    
    if upsert_rows:
        sb.table("products").upsert(upsert_rows, on_conflict="store_id,barcode").execute()
        # Clean unknown scans for added barcodes
        imported_barcodes = [c["barcode"] for c in candidates]
        try:
            sb.table("unknown_scans").delete().eq("store_id", store_id).in_("barcode", imported_barcodes).execute()
        except Exception:
            pass
            
    return ImportExecuteResponse(
        status="ok",
        added_count=parsed["to_add_count"],
        updated_count=parsed["to_update_count"],
        failed_count=parsed["to_fail_count"],
        errors=parsed["failed"]
    )

# --------------------------------------------------------------------------
# 5. Unknown-Scans Queue
# --------------------------------------------------------------------------
@router.get("/stores/{store_id}/unknown-scans", response_model=List[UnknownScanResponse])
def get_store_unknown_scans(
    store_id: str,
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """List missed scans logged for this store, newest first."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    res = sb.table("unknown_scans").select("id, store_id, barcode, count, first_seen_at, last_seen_at").eq("store_id", store_id).order("last_seen_at", desc=True).execute()
    return res.data or []

@router.delete("/stores/{store_id}/unknown-scans/{scan_id_or_barcode}")
def dismiss_unknown_scan(
    store_id: str,
    scan_id_or_barcode: str,
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """Dismisses an unknown scan row from the queue (by row ID or barcode)."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    # Delete by id or barcode
    sb.table("unknown_scans").delete().eq("store_id", store_id).or_(f"id.eq.{scan_id_or_barcode},barcode.eq.{scan_id_or_barcode}").execute()
    return {"status": "ok", "message": "Unknown scan dismissed"}

# --------------------------------------------------------------------------
# 6. Manager Dashboard
# --------------------------------------------------------------------------
@router.get("/stores/{store_id}/dashboard")
def get_manager_store_dashboard(
    store_id: str,
    date_range: str = Query("today", alias="range", description="'today' or '7d'"),
    user: Optional[UserProfile] = Depends(get_current_user)
):
    """Comprehensive store metrics: revenue, 7-day sales, top products, recent orders, low stock, SDG impact."""
    verify_manager_store_access(user, store_id)
    sb = get_supabase()
    
    # 1. Store info
    s_res = sb.table("stores").select("id, name, code, area, address").eq("id", store_id).execute()
    store = s_res.data[0] if s_res.data else {}
    
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_7d = start_today - timedelta(days=6)
    
    # 2. Orders query
    orders_res = sb.table("orders").select("id, customer_id, bill_no, total, payment_status, status, payment_method, created_at, paid_at").eq("store_id", store_id).order("created_at", desc=True).execute()
    all_orders = orders_res.data or []
    
    today_orders = [o for o in all_orders if datetime.fromisoformat(o["created_at"]) >= start_today]
    today_paid = [o for o in today_orders if o["payment_status"] == "PAID"]
    today_revenue = sum(o["total"] for o in today_paid)
    today_order_count = len(today_orders)
    
    all_paid_orders = [o for o in all_orders if o["payment_status"] == "PAID"]
    total_paid_orders_count = len(all_paid_orders)
    total_revenue_all = sum(o["total"] for o in all_paid_orders)
    
    # 3. 7-Day sales breakdown
    sales_7d = []
    sales_last_7_days = []
    for day_offset in range(7):
        day_date = (start_7d + timedelta(days=day_offset)).date()
        day_start = datetime.combine(day_date, datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        
        day_orders = [
            o for o in all_orders 
            if o["payment_status"] == "PAID" and day_start <= datetime.fromisoformat(o["created_at"]) < day_end
        ]
        day_rev = sum(o["total"] for o in day_orders)
        day_count = len(day_orders)
        d_str = day_date.strftime("%Y-%m-%d")
        disp_str = day_date.strftime("%b %d")
        day_name = day_date.strftime("%a")

        sales_7d.append({
            "date": d_str,
            "display_date": disp_str,
            "revenue": day_rev,
            "orders": day_count
        })
        sales_last_7_days.append({
            "date": d_str,
            "display_date": disp_str,
            "label": disp_str,
            "day_name": day_name,
            "sales": day_rev,
            "orders": day_count
        })
        
    # 4. Products & Low-stock list (stock <= 5)
    prods_res = sb.table("products").select("id, store_id, barcode, name, brand, category, price, mrp, stock, unit").eq("store_id", store_id).order("stock").execute()
    all_products = prods_res.data or []
    low_stock_products = [p for p in all_products if p["stock"] <= 5]
    
    # 5. Top 5 Products by Quantity Sold
    paid_order_ids = [o["id"] for o in all_paid_orders[:100]]
    prod_qty_map = defaultdict(lambda: {"name": "", "qty": 0, "revenue": 0})
    total_items_sold = 0
    if paid_order_ids:
        items_res = sb.table("order_items").select("name, price, qty").in_("order_id", paid_order_ids).execute()
        for it in (items_res.data or []):
            name = it.get("name") or "Product"
            q = it.get("qty", 1)
            p = it.get("price", 0)
            prod_qty_map[name]["name"] = name
            prod_qty_map[name]["qty"] += q
            prod_qty_map[name]["revenue"] += p * q
            total_items_sold += q
            
    top_products_raw = sorted(prod_qty_map.values(), key=lambda x: x["qty"], reverse=True)[:5]
    top_products = [
        {
            "name": p["name"],
            "qty_sold": p["qty"],
            "qty": p["qty"],
            "revenue": p["revenue"]
        }
        for p in top_products_raw
    ]
    
    # 6. Customer Names & Items Count for Recent Transactions
    customer_ids = [o["customer_id"] for o in all_orders[:15] if o.get("customer_id")]
    customer_name_map = {}
    if customer_ids:
        try:
            c_res = sb.table("profiles").select("id, email").in_("id", customer_ids).execute()
            for c in (c_res.data or []):
                email = c.get("email") or ""
                name_part = email.split("@")[0].capitalize() if email else "Customer"
                customer_name_map[c["id"]] = name_part
        except Exception:
            pass

    order_ids_15 = [o["id"] for o in all_orders[:15]]
    order_items_count_map = defaultdict(int)
    if order_ids_15:
        try:
            oi_res = sb.table("order_items").select("order_id, qty").in_("order_id", order_ids_15).execute()
            for oi in (oi_res.data or []):
                order_items_count_map[oi["order_id"]] += oi.get("qty", 1)
        except Exception:
            pass

    recent_transactions = []
    recent_orders = []
    for o in all_orders[:15]:
        ostatus = o.get("status")
        pstatus = o.get("payment_status")
        
        display_status = "Paid"
        if ostatus in ("USED", "VERIFIED"):
            display_status = "Verified"
        elif ostatus == "MISMATCH":
            display_status = "Mismatch"
        elif ostatus == "PENDING_STAFF" or pstatus == "CASH_PENDING":
            display_status = "Staff Pending"
        elif pstatus == "PAID":
            display_status = "Paid"
        else:
            display_status = "Pending"

        tx_item = {
            "id": o["id"],
            "bill_no": o.get("bill_no") or "PENDING",
            "customer_name": customer_name_map.get(o.get("customer_id"), "Customer"),
            "items_count": order_items_count_map.get(o["id"], 1),
            "total": o.get("total", 0),
            "payment_method": o.get("payment_method") or "mock_upi",
            "status": display_status,
            "created_at": o.get("created_at")
        }
        recent_transactions.append(tx_item)
        
        recent_orders.append({
            "id": o["id"],
            "bill_no": o.get("bill_no") or "PENDING",
            "total": o.get("total", 0),
            "status": o.get("status"),
            "payment_status": o.get("payment_status"),
            "payment_method": o.get("payment_method"),
            "created_at": o.get("created_at")
        })
        
    # 7. Unknown Scans count
    unk_res = sb.table("unknown_scans").select("id, count").eq("store_id", store_id).execute()
    unknown_scans_count = sum(u.get("count", 1) for u in (unk_res.data or []))
    
    # 8. SDG Impact Metrics
    queue_time_saved_minutes = total_paid_orders_count * 4
    queue_time_saved_hours = round(queue_time_saved_minutes / 60.0, 1)
    paper_bills_saved = total_paid_orders_count
    
    sales_total = today_revenue if date_range == "today" else total_revenue_all
    orders_count = today_order_count if date_range == "today" else len(all_orders)
    average_bill = round(sales_total / orders_count) if orders_count > 0 else 0

    impact_data = {
        "queue_time_saved_hours": queue_time_saved_hours,
        "queue_time_saved_minutes": queue_time_saved_minutes,
        "paper_bills_avoided": paper_bills_saved,
        "items_scanned": total_items_sold,
        "disclaimer": "Estimates calculated directly from transaction data. No AI."
    }

    return {
        "store": store,
        "sales_total": sales_total,
        "orders_count": orders_count,
        "items_sold": total_items_sold,
        "average_bill": average_bill,
        "low_stock_count": len(low_stock_products),
        "low_stock_items": low_stock_products,
        "low_stock_products": low_stock_products,
        "sales_last_7_days": sales_last_7_days,
        "sales_7d": sales_7d,
        "top_products": top_products,
        "recent_transactions": recent_transactions,
        "recent_orders": recent_orders,
        "impact": impact_data,
        "sdg_impact": {
            "queue_time_saved_minutes": queue_time_saved_minutes,
            "paper_bills_saved": paper_bills_saved,
            "label": "Estimates: ~4 min saved per Scan-and-Go checkout; 1 paper receipt saved per digital bill."
        },
        "kpis": {
            "today_orders": today_order_count,
            "today_revenue": today_revenue,
            "total_orders": len(all_orders),
            "total_revenue": total_revenue_all,
            "paid_orders": total_paid_orders_count,
            "low_stock_count": len(low_stock_products),
            "unknown_scans_count": unknown_scans_count,
            "queue_time_saved_minutes": queue_time_saved_minutes,
            "paper_bills_saved": paper_bills_saved
        }
    }

# --------------------------------------------------------------------------
# 7. Demo Reset
# --------------------------------------------------------------------------
@router.post("/demo-reset", response_model=ResetDemoResponse)
def reset_demo_data(user: Optional[UserProfile] = Depends(get_optional_user)):
    """
    Reruns the network-safe seed for schema app2026.
    Rule: Scoped to the 3 demo stores ONLY. Network stores/products/orders are untouched.
    Seed products are upserted; manager-added (custom) products in demo stores survive; demo orders return to exactly 40.
    """
    if user and user.role not in ("manager", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Access forbidden: manager role required", "code": "FORBIDDEN"}
        )
    seed.seed_database(preserve_custom_products=True)
    
    sb = get_supabase()
    s_count = sb.table("stores").select("id", count="exact").limit(1).execute().count or 0
    p_count = sb.table("products").select("id", count="exact").limit(1).execute().count or 0
    o_count = sb.table("orders").select("id", count="exact").limit(1).execute().count or 0
    
    return ResetDemoResponse(
        status="ok",
        message="Demo state reset successfully. Network stores and custom manager products preserved.",
        canonical_bill="SS-20481",
        stores_count=s_count,
        products_count=p_count,
        orders_count=o_count
    )
