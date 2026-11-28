import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from core.db import get_supabase
from core.auth import get_current_user, get_optional_user, UserProfile, require_staff_or_manager
from core.stock import decrement_order_stock_atomic
from core.rate_limit import check_checkout_rate_limit
from core.gst import compute_gst_breakup, default_gst_rate
from models.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    MockPayResponse,
    CashPayResponse,
    CashConfirmResponse,
    OrderItemResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Orders"])

def generate_bill_no() -> str:
    """Generates a unique bill number in SS-xxxxx format."""
    sb = get_supabase()
    for _ in range(25):
        num = random.randint(80000, 99999)
        candidate = f"SS-{num}"
        exists = sb.table("orders").select("id").eq("bill_no", candidate).limit(1).execute()
        if not exists.data:
            return candidate
    return f"SS-{random.randint(80000, 99999)}"

@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    req: CheckoutRequest,
    user: Optional[UserProfile] = Depends(get_optional_user),
    _rl: None = Depends(check_checkout_rate_limit)
):
    """
    Validates items and available stock against the store's catalogue.
    Computes totals STRICTLY server-side from DB prices.
    Creates ONE PENDING order.
    """
    sb = get_supabase()
    
    # 1. Verify store exists
    store_res = sb.table("stores").select("id, name, code").eq("id", req.store_id).execute()
    if not store_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Store not found", "code": "STORE_NOT_FOUND"}
        )
    
    if not req.items or len(req.items) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Cart cannot be empty", "code": "EMPTY_CART"}
        )
    
    # 2. Fetch products for this store
    barcodes = [item.barcode for item in req.items]
    prod_res = sb.table("products").select(
        "id, store_id, barcode, name, category, price, stock, gst_rate, mrp"
    ).eq("store_id", req.store_id).in_("barcode", barcodes).execute()
    
    prods_by_barcode = {p["barcode"]: p for p in (prod_res.data or [])}
    
    validated_items = []
    grand_total = 0
    
    for item in req.items:
        prod = prods_by_barcode.get(item.barcode)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": f"Product with barcode '{item.barcode}' is not sold in this store", "code": "PRODUCT_NOT_FOUND"}
            )
        
        # Rule: stock decrement is conditional, stock-0 cannot be checked out
        if prod["stock"] < item.qty or prod["stock"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Item '{prod['name']}' has insufficient stock (available: {prod['stock']}, requested: {item.qty})",
                    "code": "INSUFFICIENT_STOCK",
                    "product_name": prod["name"],
                    "available_stock": prod["stock"],
                    "requested_qty": item.qty
                }
            )
            
        line_total = prod["price"] * item.qty
        grand_total += line_total
        gst_r = prod.get("gst_rate")
        if gst_r is None:
            gst_r = default_gst_rate(prod.get("category"), prod["name"], prod["price"])
        gst_r = int(gst_r)
        mrp_val = prod.get("mrp") or prod["price"]

        validated_items.append({
            "product_id": prod["id"],
            "barcode": prod["barcode"],
            "name": prod["name"],
            "price": prod["price"],
            "mrp": mrp_val,
            "gst_rate": gst_r,
            "qty": item.qty,
            "line_total": line_total
        })
        
    customer_id = user.id if user else None
    
    # 3. Create ONE order record
    order_data = {
        "store_id": req.store_id,
        "customer_id": customer_id,
        "customer_mobile": req.customer_mobile,
        "total": grand_total,
        "payment_status": "PENDING",
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    order_ins = sb.table("orders").insert(order_data).execute()
    if not order_ins.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to create order record", "code": "ORDER_CREATE_FAILED"}
        )
    order = order_ins.data[0]
    order_id = order["id"]
    
    # 4. Insert order items snapshot
    order_item_rows = [
        {
            "order_id": order_id,
            "product_id": it["product_id"],
            "barcode": it["barcode"],
            "name": it["name"],
            "price": it["price"],
            "qty": it["qty"],
            "gst_rate": it["gst_rate"]
        }
        for it in validated_items
    ]
    sb.table("order_items").insert(order_item_rows).execute()
    
    item_count = sum(it["qty"] for it in validated_items)
    mrp_total = sum(it["mrp"] * it["qty"] for it in validated_items)
    discount = max(0, mrp_total - grand_total)

    return CheckoutResponse(
        order_id=order_id,
        store_id=req.store_id,
        total=grand_total,
        status="PENDING",
        payment_status="PENDING",
        customer_mobile=req.customer_mobile,
        item_count=item_count,
        mrp_total=mrp_total,
        discount=discount,
        items=[
            OrderItemResponse(
                product_id=it["product_id"],
                barcode=it["barcode"],
                name=it["name"],
                price=it["price"],
                mrp=it["mrp"],
                gst_rate=it["gst_rate"],
                qty=it["qty"],
                line_total=it["line_total"]
            ) for it in validated_items
        ]
    )

@router.post("/orders/{order_id}/pay/mock", response_model=MockPayResponse)
@router.post("/orders/{order_id}/mock-pay", response_model=MockPayResponse)
def mock_pay(order_id: str):
    """
    Flips the order to PAID and issues its bill (bill_no SS-xxxxx, QR token).
    Idempotent: paying twice returns the same bill; stock decrements exactly once.
    """
    sb = get_supabase()
    
    # 1. Fetch order
    res = sb.table("orders").select("id, bill_no, store_id, customer_id, customer_mobile, total, payment_method, payment_status, status, paid_at").eq("id", order_id).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Order not found", "code": "ORDER_NOT_FOUND"}
        )
    order = res.data[0]
    store_info = sb.table("stores").select("name").eq("id", order["store_id"]).limit(1).execute()
    store_name = store_info.data[0]["name"] if store_info.data else None
    
    # Fetch order items
    items_res = sb.table("order_items").select("product_id, barcode, name, price, qty, gst_rate").eq("order_id", order_id).execute()
    items_data = items_res.data or []

    prod_ids = [it["product_id"] for it in items_data if it.get("product_id")]
    prod_map = {}
    if prod_ids:
        p_res = sb.table("products").select("id, mrp").in_("id", prod_ids).execute()
        prod_map = {p["id"]: p.get("mrp") for p in (p_res.data or [])}

    for it in items_data:
        if it.get("gst_rate") is None:
            it["gst_rate"] = 5
        it["mrp"] = prod_map.get(it.get("product_id")) or it.get("price")

    breakup = compute_gst_breakup(items_data)
    item_count = sum(it.get("qty", 1) for it in items_data)
    mrp_total = sum((it.get("mrp") or it["price"]) * it.get("qty", 1) for it in items_data)
    discount = max(0, mrp_total - order["total"])

    order_items_resp = [
        OrderItemResponse(
            product_id=it["product_id"],
            barcode=it["barcode"],
            name=it["name"],
            price=it["price"],
            qty=it["qty"],
            mrp=it.get("mrp"),
            gst_rate=it.get("gst_rate", 5),
            line_total=it["price"] * it["qty"]
        ) for it in items_data
    ]
    
    # Idempotent check: if already paid, return existing bill without re-decrementing stock
    if order["payment_status"] == "PAID" and order["bill_no"]:
        return MockPayResponse(
            order_id=order["id"],
            bill_no=order["bill_no"],
            qr_token=order["bill_no"],
            total=order["total"],
            status=order["status"],
            payment_status=order["payment_status"],
            store_id=order["store_id"],
            store_name=store_name,
            paid_at=order.get("paid_at") or datetime.now(timezone.utc).isoformat(),
            customer_mobile=order.get("customer_mobile"),
            item_count=item_count,
            mrp_total=mrp_total,
            discount=discount,
            gst_breakup=breakup["breakup_rows"],
            gst_totals=breakup["totals"],
            items=order_items_resp
        )
        
    # 2. Decrement stock atomically (conditional on stock >= qty)
    decrement_order_stock_atomic(order["store_id"], items_data)
    
    # 3. Generate bill number and update order to PAID
    bill_no = generate_bill_no()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    update_res = sb.table("orders").update({
        "bill_no": bill_no,
        "payment_method": "mock_upi",
        "payment_status": "PAID",
        "status": "PAID",
        "paid_at": now_iso
    }).eq("id", order_id).execute()
    
    if not update_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to update order payment status", "code": "PAYMENT_UPDATE_FAILED"}
        )
        
    updated = update_res.data[0]
    store_info = sb.table("stores").select("name").eq("id", updated["store_id"]).limit(1).execute()
    store_name = store_info.data[0]["name"] if store_info.data else None

    return MockPayResponse(
        order_id=updated["id"],
        bill_no=updated["bill_no"],
        qr_token=updated["bill_no"],
        total=updated["total"],
        status=updated["status"],
        payment_status=updated["payment_status"],
        store_id=updated["store_id"],
        store_name=store_name,
        paid_at=updated["paid_at"],
        customer_mobile=order.get("customer_mobile"),
        item_count=item_count,
        mrp_total=mrp_total,
        discount=discount,
        gst_breakup=breakup["breakup_rows"],
        gst_totals=breakup["totals"],
        items=order_items_resp
    )

@router.post("/orders/{order_id}/pay/cash", response_model=CashPayResponse)
def cash_pay(order_id: str):
    """
    Submits order for cash payment at the exit counter.
    Flips order to CASH_PENDING.
    """
    sb = get_supabase()
    res = sb.table("orders").select("id, payment_status, total").eq("id", order_id).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Order not found", "code": "ORDER_NOT_FOUND"}
        )
    order = res.data[0]
    
    if order["payment_status"] == "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Order is already paid", "code": "ALREADY_PAID"}
        )
        
    sb.table("orders").update({
        "payment_method": "cash",
        "payment_status": "CASH_PENDING",
        "status": "CASH_PENDING"
    }).eq("id", order_id).execute()
    
    return CashPayResponse(
        order_id=order_id,
        status="CASH_PENDING",
        payment_status="CASH_PENDING",
        total=order["total"],
        message="Order placed. Please proceed to the exit staff counter for cash payment."
    )

@router.post("/orders/{order_id}/confirm-cash", response_model=CashConfirmResponse)
@router.post("/orders/{order_id}/cash-confirm", response_model=CashConfirmResponse)
def confirm_cash_payment(
    order_id: str,
    user: Optional[UserProfile] = Depends(get_optional_user)
):
    """
    Staff confirms cash payment: activates the bill and decrements stock.
    """
    sb = get_supabase()
    res = sb.table("orders").select("id, bill_no, store_id, total, payment_status, status").eq("id", order_id).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Order not found", "code": "ORDER_NOT_FOUND"}
        )
    order = res.data[0]
    
    # If already paid, return bill
    if order["payment_status"] == "PAID" and order["bill_no"]:
        return CashConfirmResponse(
            order_id=order["id"],
            bill_no=order["bill_no"],
            qr_token=order["bill_no"],
            total=order["total"],
            status=order["status"],
            payment_status=order["payment_status"],
            paid_at=order.get("paid_at") or datetime.now(timezone.utc).isoformat()
        )
        
    items_res = sb.table("order_items").select("product_id, barcode, name, price, qty").eq("order_id", order_id).execute()
    items_data = items_res.data or []
    
    # Atomic conditional stock decrement
    decrement_order_stock_atomic(order["store_id"], items_data)
    
    bill_no = generate_bill_no()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    sb.table("orders").update({
        "bill_no": bill_no,
        "payment_method": "cash",
        "payment_status": "PAID",
        "status": "PAID",
        "paid_at": now_iso
    }).eq("id", order_id).execute()
    
    return CashConfirmResponse(
        order_id=order["id"],
        bill_no=bill_no,
        qr_token=bill_no,
        total=order["total"],
        status="PAID",
        payment_status="PAID",
        paid_at=now_iso
    )

@router.get("/orders/my")
def get_my_orders(user: UserProfile = Depends(get_current_user)):
    """Returns the authenticated customer's past orders with items and store details."""
    sb = get_supabase()
    
    orders_res = sb.table("orders").select(
        "id, bill_no, store_id, total, payment_method, payment_status, status, created_at, paid_at, stores(id, name, code, area)"
    ).eq("customer_id", user.id).order("created_at", desc=True).execute()
    
    orders = orders_res.data or []
    for ord_obj in orders:
        items_res = sb.table("order_items").select("id, product_id, barcode, name, price, qty").eq("order_id", ord_obj["id"]).execute()
        ord_obj["items"] = items_res.data or []
        
    return orders

@router.get("/orders/{order_id}")
@router.get("/bills/{order_id}")
def get_order_by_id(order_id: str):
    """Fetch order details by order_id or bill_no safely avoiding UUID syntax errors."""
    sb = get_supabase()
    clean_id = order_id.strip()
    
    is_uuid = False
    try:
        uuid.UUID(clean_id)
        is_uuid = True
    except (ValueError, TypeError):
        is_uuid = False

    query = sb.table("orders").select(
        "id, bill_no, store_id, customer_id, customer_mobile, total, payment_method, payment_status, status, created_at, paid_at, stores(id, name, code, area, address)"
    )

    if is_uuid:
        res = query.eq("id", clean_id).execute()
        if not res.data:
            res = query.eq("bill_no", clean_id).execute()
    else:
        res = query.eq("bill_no", clean_id).execute()
    
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Order not found", "code": "ORDER_NOT_FOUND"}
        )
    order = res.data[0]
    items_res = sb.table("order_items").select("id, product_id, barcode, name, price, qty, gst_rate").eq("order_id", order["id"]).execute()
    items = items_res.data or []
    prod_ids = [it["product_id"] for it in items if it.get("product_id")]
    prod_map = {}
    if prod_ids:
        p_res = sb.table("products").select("id, mrp").in_("id", prod_ids).execute()
        prod_map = {p["id"]: p.get("mrp") for p in (p_res.data or [])}

    for it in items:
        if it.get("gst_rate") is None:
            it["gst_rate"] = 5
        it["mrp"] = prod_map.get(it.get("product_id")) or it.get("price")

    breakup = compute_gst_breakup(items)
    item_count = sum(it.get("qty", 1) for it in items)
    mrp_total = sum((it.get("mrp") or it["price"]) * it.get("qty", 1) for it in items)
    discount = max(0, mrp_total - order["total"])

    order["items"] = items
    order["item_count"] = item_count
    order["mrp_total"] = mrp_total
    order["discount"] = discount
    order["gst_breakup"] = breakup["breakup_rows"]
    order["gst_totals"] = breakup["totals"]
    return order
