from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Store Models
class StoreResponse(BaseModel):
    id: str
    retailer_id: Optional[str] = None
    name: str
    code: str
    area: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True

# Product Models
class ProductResponse(BaseModel):
    id: str
    store_id: str
    barcode: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    price: int
    mrp: Optional[int] = None
    stock: int
    unit: Optional[str] = None

# Scan Models
class ScanRequest(BaseModel):
    store_id: str
    barcode: str

# Checkout Models
class CheckoutItem(BaseModel):
    barcode: str
    qty: int = Field(1, ge=1)

class CheckoutRequest(BaseModel):
    store_id: str
    items: List[CheckoutItem]

class OrderItemResponse(BaseModel):
    product_id: Optional[str] = None
    barcode: Optional[str] = None
    name: str
    price: int
    qty: int
    line_total: Optional[int] = None

class CheckoutResponse(BaseModel):
    order_id: str
    store_id: str
    total: int
    status: str
    payment_status: str
    items: List[OrderItemResponse]

# Pay Models
class MockPayResponse(BaseModel):
    order_id: str
    bill_no: str
    qr_token: str
    total: int
    status: str
    payment_status: str
    store_id: str
    paid_at: str
    items: List[OrderItemResponse]

class CashPayResponse(BaseModel):
    order_id: str
    status: str
    payment_status: str
    total: int
    message: str

class CashConfirmResponse(BaseModel):
    order_id: str
    bill_no: str
    qr_token: str
    total: int
    status: str
    payment_status: str
    paid_at: str

# Exit Verification Models
class ExitVerifyRequest(BaseModel):
    bill_no: str

class ExitVerifyResponse(BaseModel):
    result: str  # VERIFIED, ALREADY_USED, INVALID, UNPAID
    bill_no: Optional[str] = None
    order_id: Optional[str] = None
    store_name: Optional[str] = None
    store_code: Optional[str] = None
    total: Optional[int] = None
    paid_at: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None

class ExitUseRequest(BaseModel):
    bill_no: str

class ExitUseResponse(BaseModel):
    status: str
    bill_no: str
    message: str

# Profile / Auth Models
class UserProfileResponse(BaseModel):
    id: str
    email: Optional[str] = None
    role: str
    store_id: Optional[str] = None
    store: Optional[Dict[str, Any]] = None
