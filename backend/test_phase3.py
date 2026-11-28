"""
SmartScan 2026 — Phase 3 Acceptance & Verification Tests
Targets schema: app2026 exclusively.

Verifies:
1. Network-safe demo reset:
   - Stores count remains 103 (network stores untouched)
   - Network products count remains 3,300 (untouched)
   - Network orders count remains 9,924 (untouched)
   - Demo orders return to exactly 40
   - Canonical bill SS-20481 is present, total Rs 317, status USED
   - Coca-Cola stock is reset to 0
2. Regression:
   - Phase 1 acceptance tests (7/7 PASS)
   - Phase 2 acceptance tests (8/8 PASS)
3. Network store API checkout verification:
   - Select network store (e.g. NW02 in Clement Town)
   - Check out real product
   - Complete payment and verify bill generated
"""

import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.testclient import TestClient
from main import app
from core.db import get_supabase
from core.auth import UserProfile, get_current_user
import test_phase1
import test_phase2

client = TestClient(app)

def run_phase3_tests():
    print("=" * 65)
    print("SMARTSCAN 2026 — PHASE 3 ACCEPTANCE & NETWORK VERIFICATION TESTS")
    print("=" * 65)

    sb = get_supabase()
    results = {}

    demo_store_ids = [
        "a1535a5c-50e7-4415-a855-ac792e016158", # FreshMart
        "c45044cd-ef16-4113-8b26-d21fcfa8a99b", # StyleHub
        "f79f8f33-5499-48c7-97b6-506499fac73e"  # DailyNeeds
    ]

    # -------------------------------------------------------------
    # Step 0: Record Baseline Counts
    # -------------------------------------------------------------
    print("\n[Step 0] Recording baseline database counts in app2026...")
    init_stores = sb.table("stores").select("id", count="exact").limit(1).execute().count or 0
    init_net_prods = sb.table("products").select("id", count="exact").not_.in_("store_id", demo_store_ids).execute().count or 0
    init_net_orders = sb.table("orders").select("id", count="exact").not_.in_("store_id", demo_store_ids).execute().count or 0
    init_demo_orders = sb.table("orders").select("id", count="exact").in_("store_id", demo_store_ids).execute().count or 0

    print(f"-> Total stores: {init_stores}")
    print(f"-> Network products (100 stores): {init_net_prods}")
    print(f"-> Network orders: {init_net_orders}")
    print(f"-> Demo orders (FM, SH, DN): {init_demo_orders}")

    assert init_stores == 103, f"Expected 103 stores, found {init_stores}"
    assert init_net_prods == 3300, f"Expected 3300 network products, found {init_net_prods}"
    assert init_net_orders == 9924, f"Expected 9924 network orders, found {init_net_orders}"

    # -------------------------------------------------------------
    # Test 1: Network-Safe Demo Reset
    # -------------------------------------------------------------
    print("\n[Test 1] Executing network-safe demo reset (POST /manager/demo-reset)...")
    mock_manager = UserProfile(
        id="demo-manager-id",
        email="manager@smartscan.app",
        role="manager",
        store_id="a1535a5c-50e7-4415-a855-ac792e016158"
    )
    app.dependency_overrides[get_current_user] = lambda: mock_manager
    try:
        reset_res = client.post("/manager/demo-reset")
        assert reset_res.status_code == 200, f"Demo reset failed: {reset_res.text}"
        reset_json = reset_res.json()
        print(f"-> Reset API Response: {reset_json['message']}")
    finally:
        app.dependency_overrides.clear()

    # Verify counts post-reset
    post_stores = sb.table("stores").select("id", count="exact").limit(1).execute().count or 0
    post_net_prods = sb.table("products").select("id", count="exact").not_.in_("store_id", demo_store_ids).execute().count or 0
    post_net_orders = sb.table("orders").select("id", count="exact").not_.in_("store_id", demo_store_ids).execute().count or 0
    post_demo_orders = sb.table("orders").select("id", count="exact").in_("store_id", demo_store_ids).execute().count or 0

    print(f"-> Post-reset stores count: {post_stores} (expected 103)")
    print(f"-> Post-reset network products: {post_net_prods} (expected 3300)")
    print(f"-> Post-reset network orders: {post_net_orders} (expected 9924)")
    print(f"-> Post-reset demo orders: {post_demo_orders} (expected exactly 40)")

    assert post_stores == 103, f"Stores changed! Expected 103, got {post_stores}"
    assert post_net_prods == 3300, f"Network products altered! Expected 3300, got {post_net_prods}"
    assert post_net_orders == 9924, f"Network orders altered! Expected 9924, got {post_net_orders}"
    assert post_demo_orders == 40, f"Demo orders count mismatch! Expected 40, got {post_demo_orders}"

    # Verify canonical bill SS-20481
    can_res = client.get("/bills/SS-20481")
    assert can_res.status_code == 200, f"Failed to fetch canonical bill SS-20481: {can_res.text}"
    can_data = can_res.json()
    assert can_data["total"] == 317, f"Canonical total mismatch: {can_data['total']}"
    assert can_data["status"] == "USED", f"Canonical status mismatch: {can_data['status']}"
    print(f"-> Canonical bill SS-20481 verified: Total=Rs {can_data['total']}, Status={can_data['status']}")

    # Verify Coca-Cola stock reset to 0
    coke = sb.table("products").select("stock").eq("store_id", "a1535a5c-50e7-4415-a855-ac792e016158").eq("barcode", "8901764012296").execute()
    assert coke.data and coke.data[0]["stock"] == 0, f"Coca-Cola stock not reset to 0: {coke.data}"
    print("-> Coca-Cola stock verified at 0")

    results["Test 1 (Network-Safe Demo Reset)"] = f"PASS (Stores: {post_stores}/103, Net Prods: {post_net_prods}/3300, Net Orders: {post_net_orders}/9924, Demo Orders: {post_demo_orders}/40, SS-20481: Rs 317)"

    # -------------------------------------------------------------
    # Test 2: Network Store API Checkout
    # -------------------------------------------------------------
    print("\n[Test 2] Network store checkout flow (Clement Town NW02)...")
    nw02_stores = sb.table("stores").select("id, name").eq("code", "NW02").execute()
    assert nw02_stores.data, "NW02 store not found in database!"
    nw02_id = nw02_stores.data[0]["id"]

    # Pick a product in NW02 with stock
    nw02_prods = sb.table("products").select("id, barcode, name, price, stock").eq("store_id", nw02_id).gt("stock", 5).limit(1).execute()
    assert nw02_prods.data, "No stock found in NW02!"
    prod = nw02_prods.data[0]
    print(f"-> Testing checkout at {nw02_stores.data[0]['name']} for '{prod['name']}' (Rs {prod['price']})")

    # Checkout
    co_res = client.post("/checkout", json={
        "store_id": nw02_id,
        "items": [{"barcode": prod["barcode"], "qty": 1}]
    })
    assert co_res.status_code == 200, f"Checkout failed: {co_res.text}"
    co_data = co_res.json()
    order_id = co_data["order_id"]
    print(f"-> Network store order placed: {order_id}, total: Rs {co_data['total']}")

    # Pay
    pay_res = client.post(f"/orders/{order_id}/pay/mock", json={
        "payment_method": "mock_upi",
        "mock_status": "SUCCESS"
    })
    assert pay_res.status_code == 200, f"Payment failed: {pay_res.text}"
    bill_no = pay_res.json()["bill_no"]
    print(f"-> Payment successful. Digital bill issued: {bill_no}")

    # Exit verify
    verify_res = client.post("/exit/verify", json={"bill_no": bill_no})
    assert verify_res.status_code == 200
    assert verify_res.json()["result"] == "VERIFIED"
    print(f"-> Exit verification verdict: {verify_res.json()['result']}")

    # Clean up test order from NW02 so network orders remain at baseline (9924)
    sb.table("exit_verifications").delete().eq("bill_no", bill_no).execute()
    sb.table("order_items").delete().eq("order_id", order_id).execute()
    sb.table("orders").delete().eq("id", order_id).execute()

    results["Test 2 (Network Store Checkout API)"] = f"PASS (Order: {order_id}, Bill: {bill_no}, Exit: VERIFIED)"

    # -------------------------------------------------------------
    # Test 3: Regression Suite Phase 1 (7/7)
    # -------------------------------------------------------------
    print("\n[Test 3] Regression: Running Phase 1 test suite...")
    p1 = test_phase1.run_acceptance_tests()
    p1_pass = sum(1 for v in p1.values() if v.startswith("PASS"))
    p1_tot = len(p1)
    print(f"-> Phase 1 results: {p1_pass}/{p1_tot} passed")
    assert p1_pass == p1_tot, f"Phase 1 regression failure! {p1}"
    results["Test 3 (Phase 1 Regression)"] = f"PASS ({p1_pass}/{p1_tot} passed)"

    # -------------------------------------------------------------
    # Test 4: Regression Suite Phase 2 (8/8)
    # -------------------------------------------------------------
    print("\n[Test 4] Regression: Running Phase 2 test suite...")
    p2 = test_phase2.run_phase2_tests()
    p2_pass = sum(1 for v in p2.values() if v.startswith("PASS"))
    p2_tot = len(p2)
    print(f"-> Phase 2 results: {p2_pass}/{p2_tot} passed")
    assert p2_pass == p2_tot, f"Phase 2 regression failure! {p2}"
    results["Test 4 (Phase 2 Regression)"] = f"PASS ({p2_pass}/{p2_tot} passed)"

    print("\n" + "=" * 65)
    print("ALL PHASE 3 VERIFICATION RESULTS SUMMARY")
    print("=" * 65)
    for k, v in results.items():
        print(f"{k}: {v}")
    print("=" * 65)
    return results

if __name__ == "__main__":
    run_phase3_tests()
