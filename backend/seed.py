"""
SmartScan 2026 — Database Seed & Reset Script
Targets schema: app2026 exclusively.
Does NOT read or modify the public schema.

Seeding:
- 3 stores: FreshMart (FM), StyleHub (SH), DailyNeeds (DN)
- 16 products total (FM: 8, SH: 4, DN: 4)
- Demo accounts in Supabase Auth & app2026.profiles
- 40 past orders for rich history & KPI verification
- Canonical cart: Milk (62) + Bread (45) + Shampoo (210) = 317 INR
- Multi-store pricing for Bottle: FM = 499 INR, SH = 549 INR
- Out of stock item at FM: Coca-Cola (stock = 0)
"""

import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import httpx
from dotenv import load_dotenv
from supabase import create_client, ClientOptions

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
DEMO_PASSWORD = "SmartScanDemo2026!"
SCHEMA = "app2026"

def get_supabase_client():
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
        options=ClientOptions(schema=SCHEMA)
    )

def create_or_get_user(client: httpx.Client, email: str, display_name: str) -> str:
    """Lookup or create user via Supabase Auth Admin API (Auth has no schema)."""
    admin_url = f"{SUPABASE_URL}/auth/v1/admin/users"
    auth_headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. First search existing users by email
    list_res = client.get(f"{admin_url}?per_page=100", headers=auth_headers)
    if list_res.status_code == 200:
        users = list_res.json().get("users", [])
        for u in users:
            if u.get("email", "").lower() == email.lower():
                user_id = u["id"]
                # Ensure demo password works
                client.put(
                    f"{admin_url}/{user_id}",
                    json={"password": DEMO_PASSWORD, "email_confirm": True, "user_metadata": {"display_name": display_name}},
                    headers=auth_headers
                )
                return user_id
                
    # 2. If not found, create new auth user
    payload = {
        "email": email,
        "password": DEMO_PASSWORD,
        "email_confirm": True,
        "user_metadata": {"display_name": display_name}
    }
    res = client.post(admin_url, json=payload, headers=auth_headers)
    if res.status_code in (200, 201):
        return res.json()["id"]
        
    raise RuntimeError(f"Failed to create or retrieve auth user {email}: HTTP {res.status_code}")

SEED_BARCODES = {
    "8901262010015",  # Milk
    "8901063142217",  # Bread
    "4902430752108",  # Shampoo
    "8901234567890",  # Bottle (FM & SH)
    "8904043901005",  # Tata Salt
    "8901764012296",  # Coca-Cola (stock 0)
    "8901058852309",  # Maggi
    "8906007281223",  # Fortune Oil
    "8907263011002",  # T-Shirt
    "8907263012016",  # Jeans
    "8907263013020",  # Backpack
    "8901719101037",  # Parle-G
    "8901396387002",  # Dettol
    "8901030383322",  # Red Label Tea
    "8901030023013",  # Surf Excel
}

def seed_database(preserve_custom_products: bool = False):
    print(f"--- [SmartScan 2026 Seed] Starting network-safe demo seed for schema: {SCHEMA} (preserve_custom_products={preserve_custom_products}) ---")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")

    sb = get_supabase_client()

    # 1. Ensure Retailer and 3 Demo Stores (FreshMart, StyleHub, DailyNeeds)
    print("1/5 Ensuring Retailer and 3 Demo Stores (FreshMart, StyleHub, DailyNeeds)...")
    existing_stores = sb.table("stores").select("id, code").in_("code", ["FM", "SH", "DN"]).execute()
    stores_map = {}
    if existing_stores.data:
        stores_map = {s["code"]: s["id"] for s in existing_stores.data}
    
    if not stores_map or "FM" not in stores_map or "SH" not in stores_map or "DN" not in stores_map:
        ret_res = sb.table("retailers").select("id").limit(1).execute()
        if ret_res.data:
            retailer_id = ret_res.data[0]["id"]
        else:
            ret_ins = sb.table("retailers").insert({"name": "SmartScan Demo Retail"}).execute()
            retailer_id = ret_ins.data[0]["id"]

        stores_data = [
            {
                "retailer_id": retailer_id,
                "name": "FreshMart",
                "code": "FM",
                "area": "Rajpur Road, Dehradun",
                "address": "14 Rajpur Road, Near Clock Tower, Dehradun",
                "is_active": True
            },
            {
                "retailer_id": retailer_id,
                "name": "StyleHub",
                "code": "SH",
                "area": "Rajpur Road, Dehradun",
                "address": "48 Rajpur Road, Dehradun",
                "is_active": True
            },
            {
                "retailer_id": retailer_id,
                "name": "DailyNeeds",
                "code": "DN",
                "area": "Subhash Nagar, Dehradun",
                "address": "9 Subhash Nagar, Dehradun",
                "is_active": True
            }
        ]
        stores_res = sb.table("stores").upsert(stores_data, on_conflict="code").execute()
        for s in (stores_res.data or []):
            stores_map[s["code"]] = s["id"]
        
    fm_id = stores_map["FM"]
    sh_id = stores_map["SH"]
    dn_id = stores_map["DN"]
    demo_store_ids = [fm_id, sh_id, dn_id]

    # 2. Clean existing DEMO-ONLY data in schema app2026 (Network stores, products, orders are UNTOUCHED)
    print("2/5 Cleaning existing demo store orders and unknown scans (scoped to FM, SH, DN)...")
    try:
        # Fetch order IDs belonging to the 3 demo stores
        demo_orders_res = sb.table("orders").select("id").in_("store_id", demo_store_ids).execute()
        demo_order_ids = [o["id"] for o in (demo_orders_res.data or [])]

        if demo_order_ids:
            chunk_size = 50
            for i in range(0, len(demo_order_ids), chunk_size):
                chunk = demo_order_ids[i:i + chunk_size]
                sb.table("exit_verifications").delete().in_("order_id", chunk).execute()
                sb.table("order_items").delete().in_("order_id", chunk).execute()

        sb.table("exit_verifications").delete().eq("bill_no", "SS-20481").execute()
        sb.table("orders").delete().in_("store_id", demo_store_ids).execute()
        sb.table("unknown_scans").delete().in_("store_id", demo_store_ids).execute()

        if not preserve_custom_products:
            sb.table("products").delete().in_("store_id", demo_store_ids).not_.in_("barcode", list(SEED_BARCODES)).execute()
    except Exception as e:
        print(f"Warning during demo table cleanup: {e}")
        
    fm_id = stores_map["FM"]
    sh_id = stores_map["SH"]
    dn_id = stores_map["DN"]

    # 3. Products (16 total: 8 FM, 4 SH, 4 DN)
    print("3/5 Seeding 16 products across 3 stores...")
    products_data = [
        # FreshMart (8 products)
        {
            "store_id": fm_id,
            "barcode": "8901262010015",
            "name": "Amul Taaza Milk 500ml",
            "brand": "Amul",
            "category": "Dairy",
            "price": 62,
            "mrp": 65,
            "stock": 45,
            "unit": "500ml"
        },
        {
            "store_id": fm_id,
            "barcode": "8901063142217",
            "name": "Britannia Whole Wheat Bread",
            "brand": "Britannia",
            "category": "Bakery",
            "price": 45,
            "mrp": 50,
            "stock": 30,
            "unit": "400g"
        },
        {
            "store_id": fm_id,
            "barcode": "4902430752108",
            "name": "Head & Shoulders Shampoo 340ml",
            "brand": "Head & Shoulders",
            "category": "Personal Care",
            "price": 210,
            "mrp": 235,
            "stock": 25,
            "unit": "340ml"
        },
        {
            "store_id": fm_id,
            "barcode": "8901234567890",
            "name": "Steel Water Bottle 1L",
            "brand": "Milton",
            "category": "Home & Kitchen",
            "price": 499,
            "mrp": 599,
            "stock": 15,
            "unit": "1L"
        },
        {
            "store_id": fm_id,
            "barcode": "8904043901005",
            "name": "Tata Salt 1kg",
            "brand": "Tata",
            "category": "Groceries",
            "price": 28,
            "mrp": 30,
            "stock": 50,
            "unit": "1kg"
        },
        {
            "store_id": fm_id,
            "barcode": "8901764012296",
            "name": "Coca-Cola 750ml",
            "brand": "Coca-Cola",
            "category": "Beverages",
            "price": 40,
            "mrp": 45,
            "stock": 0,  # Out of stock test product
            "unit": "750ml"
        },
        {
            "store_id": fm_id,
            "barcode": "8901058852309",
            "name": "Maggi 2-Minute Noodles 280g",
            "brand": "Nestle",
            "category": "Snacks",
            "price": 48,
            "mrp": 55,
            "stock": 60,
            "unit": "280g"
        },
        {
            "store_id": fm_id,
            "barcode": "8906007281223",
            "name": "Fortune Sunlite Sunflower Oil 1L",
            "brand": "Fortune",
            "category": "Groceries",
            "price": 145,
            "mrp": 165,
            "stock": 20,
            "unit": "1L"
        },

        # StyleHub (4 products)
        {
            "store_id": sh_id,
            "barcode": "8901234567890",  # Same barcode, different price at SH!
            "name": "Steel Water Bottle 1L",
            "brand": "Milton",
            "category": "Accessories",
            "price": 549,
            "mrp": 599,
            "stock": 12,
            "unit": "1L"
        },
        {
            "store_id": sh_id,
            "barcode": "8907263011002",
            "name": "Cotton Crew Neck T-Shirt M",
            "brand": "StyleHub Basics",
            "category": "Apparel",
            "price": 499,
            "mrp": 799,
            "stock": 35,
            "unit": "1 pc"
        },
        {
            "store_id": sh_id,
            "barcode": "8907263012016",
            "name": "Slim Fit Denim Jeans 32",
            "brand": "StyleHub Denim",
            "category": "Apparel",
            "price": 1299,
            "mrp": 1999,
            "stock": 18,
            "unit": "1 pc"
        },
        {
            "store_id": sh_id,
            "barcode": "8907263013020",
            "name": "Canvas Backpack Navy",
            "brand": "StyleHub Gear",
            "category": "Accessories",
            "price": 899,
            "mrp": 1299,
            "stock": 10,
            "unit": "1 pc"
        },

        # DailyNeeds (4 products)
        {
            "store_id": dn_id,
            "barcode": "8901719101037",
            "name": "Parle-G Gold Biscuits 1kg",
            "brand": "Parle",
            "category": "Snacks",
            "price": 90,
            "mrp": 100,
            "stock": 40,
            "unit": "1kg"
        },
        {
            "store_id": dn_id,
            "barcode": "8901396387002",
            "name": "Dettol Original Liquid Handwash 200ml",
            "brand": "Dettol",
            "category": "Personal Care",
            "price": 85,
            "mrp": 99,
            "stock": 25,
            "unit": "200ml"
        },
        {
            "store_id": dn_id,
            "barcode": "8901030383322",
            "name": "Brooke Bond Red Label Tea 500g",
            "brand": "Brooke Bond",
            "category": "Beverages",
            "price": 230,
            "mrp": 260,
            "stock": 30,
            "unit": "500g"
        },
        {
            "store_id": dn_id,
            "barcode": "8901030023013",
            "name": "Surf Excel Easy Wash 1kg",
            "brand": "Surf Excel",
            "category": "Household",
            "price": 135,
            "mrp": 150,
            "stock": 30,
            "unit": "1kg"
        }
    ]
    prods_res = sb.table("products").upsert(products_data, on_conflict="store_id,barcode").execute()
    print(f"Upserted {len(prods_res.data)} products successfully.")

    # 4. Auth Users and Profiles in app2026.profiles
    print("4/5 Ensuring demo Auth users & app2026.profiles...")
    existing_profiles = sb.table("profiles").select("id, email, role, store_id").execute().data or []
    prof_by_email = {p.get("email"): p for p in existing_profiles if p.get("email")}

    if len(prof_by_email) >= 5 and "demo@smartscan.app" in prof_by_email and "staff@smartscan.app" in prof_by_email:
        demo_cust_id = prof_by_email["demo@smartscan.app"]["id"]
        anubhav_cust_id = prof_by_email["anubhav@smartscan.app"]["id"]
        staff_id = prof_by_email["staff@smartscan.app"]["id"]
        manager_id = prof_by_email["manager@smartscan.app"]["id"]
        manager_sh_id = prof_by_email["manager-sh@smartscan.app"]["id"]
    else:
        with httpx.Client(timeout=30.0) as http_client:
            demo_cust_id = create_or_get_user(http_client, "demo@smartscan.app", "Demo Customer")
            anubhav_cust_id = create_or_get_user(http_client, "anubhav@smartscan.app", "Anubhav Kumar")
            staff_id = create_or_get_user(http_client, "staff@smartscan.app", "FreshMart Exit Staff")
            manager_id = create_or_get_user(http_client, "manager@smartscan.app", "FreshMart Store Manager")
            manager_sh_id = create_or_get_user(http_client, "manager-sh@smartscan.app", "StyleHub Store Manager")

        profiles_data = [
            {"id": demo_cust_id, "email": "demo@smartscan.app", "role": "customer", "store_id": None},
            {"id": anubhav_cust_id, "email": "anubhav@smartscan.app", "role": "customer", "store_id": None},
            {"id": staff_id, "email": "staff@smartscan.app", "role": "exit_staff", "store_id": fm_id},
            {"id": manager_id, "email": "manager@smartscan.app", "role": "manager", "store_id": fm_id},
            {"id": manager_sh_id, "email": "manager-sh@smartscan.app", "role": "manager", "store_id": sh_id},
        ]
        for p in profiles_data:
            sb.table("profiles").upsert(p).execute()
        print("Provisioned 5 profiles in app2026.profiles.")

    # 5. 40 Past Orders for Historical KPIs
    print("5/5 Generating 40 past orders across stores...")
    now = datetime.now(timezone.utc)
    
    # Pre-fetch product lists per store for realistic past orders
    fm_prods = [p for p in prods_res.data if p["store_id"] == fm_id and p["stock"] > 0]
    sh_prods = [p for p in prods_res.data if p["store_id"] == sh_id and p["stock"] > 0]
    dn_prods = [p for p in prods_res.data if p["store_id"] == dn_id and p["stock"] > 0]

    all_store_prods = {
        fm_id: fm_prods,
        sh_id: sh_prods,
        dn_id: dn_prods
    }

    # Ensure canonical bill SS-20481 is included in past orders
    canonical_items = [
        {"name": "Amul Taaza Milk 500ml", "barcode": "8901262010015", "price": 62, "qty": 1},
        {"name": "Britannia Whole Wheat Bread", "barcode": "8901063142217", "price": 45, "qty": 1},
        {"name": "Head & Shoulders Shampoo 340ml", "barcode": "4902430752108", "price": 210, "qty": 1}
    ]
    canonical_order_id = str(uuid.uuid4())
    canonical_order = {
        "id": canonical_order_id,
        "store_id": fm_id,
        "customer_id": demo_cust_id,
        "bill_no": "SS-20481",
        "total": 317,
        "payment_method": "mock_upi",
        "payment_status": "PAID",
        "status": "USED",
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "paid_at": (now - timedelta(hours=2)).isoformat()
    }

    # Generate remaining 39 orders over past 7 days
    orders_to_create = 39
    customer_ids = [demo_cust_id, anubhav_cust_id]
    
    orders_batch = [canonical_order]
    items_batch = [
        {
            "order_id": canonical_order_id,
            "name": it["name"],
            "barcode": it["barcode"],
            "price": it["price"],
            "qty": it["qty"]
        }
        for it in canonical_items
    ]

    demo_bill_counter = 20001
    for i in range(orders_to_create):
        store_choice = random.choices([fm_id, sh_id, dn_id], weights=[0.55, 0.25, 0.20])[0]
        avail_prods = all_store_prods[store_choice]
        picked_prods = random.sample(avail_prods, k=random.randint(1, min(3, len(avail_prods))))
        
        order_total = sum(p["price"] for p in picked_prods)
        if demo_bill_counter == 20481:
            demo_bill_counter += 1
        bill_num = f"SS-{demo_bill_counter}"
        demo_bill_counter += 1

        days_ago = random.uniform(0.1, 6.9)
        order_time = (now - timedelta(days=days_ago)).isoformat()
        oid = str(uuid.uuid4())

        orders_batch.append({
            "id": oid,
            "store_id": store_choice,
            "customer_id": random.choice(customer_ids),
            "bill_no": bill_num,
            "total": order_total,
            "payment_method": "mock_upi",
            "payment_status": "PAID",
            "status": "PAID",
            "created_at": order_time,
            "paid_at": order_time
        })

        for p in picked_prods:
            items_batch.append({
                "order_id": oid,
                "product_id": p["id"],
                "barcode": p["barcode"],
                "name": p["name"],
                "price": p["price"],
                "qty": 1
            })

    # Bulk insert all 40 orders and their items in 2 fast queries
    sb.table("orders").insert(orders_batch).execute()
    sb.table("order_items").insert(items_batch).execute()

    # Verification for canonical order
    sb.table("exit_verifications").insert({
        "order_id": canonical_order_id,
        "bill_no": "SS-20481",
        "result": "VERIFIED",
        "verified_by": staff_id,
        "created_at": (now - timedelta(hours=1, minutes=55)).isoformat()
    }).execute()

    print("--- [SmartScan 2026 Seed] Completed successfully! ---")
    print("Summary:")
    print(f"- Schema: {SCHEMA}")
    print(f"- Stores: 3 (FreshMart: {fm_id}, StyleHub: {sh_id}, DailyNeeds: {dn_id})")
    print("- Products: 16 total (FM: 8, SH: 4, DN: 4)")
    print("- Past Orders: 40 (including canonical SS-20481 at 317 INR)")
    print("- Demo Accounts: 5 (shared password: SmartScanDemo2026!)")

if __name__ == "__main__":
    seed_database()
