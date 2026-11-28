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

class ProductCreateRequest(BaseModel):
    barcode: str = Field(..., min_length=1, description="Barcode for the product")
    name: str = Field(..., min_length=1, description="Product title / name")
    brand: Optional[str] = None
    category: Optional[str] = "General"
    price: int = Field(..., ge=0, description="Price in whole INR")
    mrp: Optional[int] = Field(None, ge=0)
    stock: int = Field(..., ge=0, description="Available stock units")
    unit: Optional[str] = None

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    price: Optional[int] = Field(None, ge=0)
    mrp: Optional[int] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None

# Bulk Import Models
class ImportRowError(BaseModel):
    row: int
    barcode: Optional[str] = None
    name: Optional[str] = None
    reason: str

class ImportPreviewResponse(BaseModel):
    total_rows: int
    valid_count: int
    to_add_count: int
    to_update_count: int
    to_fail_count: int
    to_add: List[Dict[str, Any]] = []
    to_update: List[Dict[str, Any]] = []
    failed: List[ImportRowError] = []

class ImportExecuteResponse(BaseModel):
    status: str = "ok"
    added_count: int
    updated_count: int
    failed_count: int
    errors: List[ImportRowError] = []

# Unknown Scans Model
class UnknownScanResponse(BaseModel):
    id: str
    store_id: str
    barcode: str
    count: int
    first_seen_at: str
    last_seen_at: str

# Demo Reset Model
class ResetDemoResponse(BaseModel):
    status: str = "ok"
    message: str
    canonical_bill: str = "SS-20481"
    stores_count: int = 3
    products_count: int = 16
    orders_count: int = 40

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
    store_name: Optional[str] = None
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
    bill_no: Optional[str] = None
    bill_id: Optional[str] = None

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
    bill_no: Optional[str] = None
    bill_id: Optional[str] = None

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
