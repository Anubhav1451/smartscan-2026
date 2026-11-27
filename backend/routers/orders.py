import logging
import random
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from core.db import get_supabase
from core.auth import get_current_user, get_optional_user, UserProfile, require_staff_or_manager
from core.stock import decrement_order_stock_atomic
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
    """Generates a bill number in SS-xxxxx format."""
    num = random.randint(10000, 99999)
    return f"SS-{num}"

@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    req: CheckoutRequest,
    user: Optional[UserProfile] = Depends(get_optional_user)
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
        "id, store_id, barcode, name, price, stock"
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
        validated_items.append({
            "product_id": prod["id"],
            "barcode": prod["barcode"],
            "name": prod["name"],
            "price": prod["price"],
            "qty": item.qty,
            "line_total": line_total
        })
        
    customer_id = user.id if user else None
    
    # 3. Create ONE order record
    order_data = {
        "store_id": req.store_id,
        "customer_id": customer_id,
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
            "qty": it["qty"]
        }
        for it in validated_items
    ]
    sb.table("order_items").insert(order_item_rows).execute()
    
    return CheckoutResponse(
        order_id=order_id,
        store_id=req.store_id,
        total=grand_total,
        status="PENDING",
        payment_status="PENDING",
        items=[
            OrderItemResponse(
                product_id=it["product_id"],
                barcode=it["barcode"],
                name=it["name"],
                price=it["price"],
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
    res = sb.table("orders").select("id, bill_no, store_id, customer_id, total, payment_method, payment_status, status, paid_at").eq("id", order_id).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Order not found", "code": "ORDER_NOT_FOUND"}
        )
    order = res.data[0]
    
    # Fetch order items
    items_res = sb.table("order_items").select("product_id, barcode, name, price, qty").eq("order_id", order_id).execute()
    items_data = items_res.data or []
    order_items_resp = [
        OrderItemResponse(
            product_id=it["product_id"],
            barcode=it["barcode"],
            name=it["name"],
            price=it["price"],
            qty=it["qty"],
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
            paid_at=order.get("paid_at") or datetime.now(timezone.utc).isoformat(),
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
    return MockPayResponse(
        order_id=updated["id"],
        bill_no=updated["bill_no"],
        qr_token=updated["bill_no"],
        total=updated["total"],
        status=updated["status"],
        payment_status=updated["payment_status"],
        store_id=updated["store_id"],
        paid_at=updated["paid_at"],
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
    """Fetch order details by order_id or bill_no."""
    sb = get_supabase()
    res = sb.table("orders").select(
        "id, bill_no, store_id, customer_id, total, payment_method, payment_status, status, created_at, paid_at, stores(id, name, code, area, address)"
    ).or_(f"id.eq.{order_id},bill_no.eq.{order_id}").execute()
    
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Order not found", "code": "ORDER_NOT_FOUND"}
        )
    order = res.data[0]
    items_res = sb.table("order_items").select("id, product_id, barcode, name, price, qty").eq("order_id", order["id"]).execute()
    order["items"] = items_res.data or []
    return order
