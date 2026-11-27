"""
SmartScan 2026 — Phase 1 Acceptance Tests
Executes all 7 acceptance checks from docs/BUILD_PROMPT_PHASE1.md:
0. Connection proof: GET /stores returns exactly 3 seeded demo stores (not ~103 from public schema)
1. Canonical cart at FreshMart (Milk + Bread + Shampoo) totals exactly ₹317; mock pay issues bill; exit verify = VERIFIED; verify after use = ALREADY_USED; fake bill SS-99999 = INVALID
2. Double checkout/pay of the same cart creates one order, one bill, stock drops once
3. Bottle scan shows ₹499 at FreshMart and ₹549 at StyleHub
4. Stock-0 product cannot be checked out
5. Cash flow: checkout with cash -> staff confirms -> bill activates -> exit verify passes
6. Manager cross-store isolation: Manager of FM calling SH manager API gets 403
"""

import sys
import os
from starlette.testclient import TestClient
from main import app
from core.db import get_supabase
from core.auth import UserProfile, get_current_user

client = TestClient(app)

def run_acceptance_tests():
    print("=" * 60)
    print("SMARTSCAN 2026 — PHASE 1 ACCEPTANCE TESTS")
    print("=" * 60)
    
    results = {}
    
    # -------------------------------------------------------------
    # Test 0: Connection Proof (app2026 schema isolation)
    # -------------------------------------------------------------
    print("\n[Test 0] Connection proof: GET /stores")
    res = client.get("/stores")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    stores = res.json()
    store_count = len(stores)
    print(f"-> Found {store_count} stores: {[s['name'] + ' (' + s['code'] + ')' for s in stores]}")
    if store_count != 3:
        print(f"FAILED: Expected exactly 3 demo stores in app2026, but got {store_count}!")
        if store_count > 10:
            print("ALERT: Client is reading the old 'public' schema! Fix schema config.")
        results["Test 0 (Connection proof)"] = f"FAIL (got {store_count} stores, expected 3)"
        return results
    else:
        results["Test 0 (Connection proof)"] = f"PASS (exact 3 stores in app2026)"
        
    stores_by_code = {s["code"]: s for s in stores}
    fm_id = stores_by_code["FM"]["id"]
    sh_id = stores_by_code["SH"]["id"]
    dn_id = stores_by_code["DN"]["id"]

    # -------------------------------------------------------------
    # Test 3: Bottle scan multi-store pricing
    # -------------------------------------------------------------
    print("\n[Test 3] Bottle scan multi-store pricing")
    bottle_barcode = "8901234567890"
    
    scan_fm = client.post("/scan", json={"store_id": fm_id, "barcode": bottle_barcode})
    assert scan_fm.status_code == 200, f"FM bottle scan failed: {scan_fm.text}"
    fm_price = scan_fm.json()["price"]
    print(f"-> FreshMart bottle price: ₹{fm_price}")
    
    scan_sh = client.post("/scan", json={"store_id": sh_id, "barcode": bottle_barcode})
    assert scan_sh.status_code == 200, f"SH bottle scan failed: {scan_sh.text}"
    sh_price = scan_sh.json()["price"]
    print(f"-> StyleHub bottle price: ₹{sh_price}")
    
    if fm_price == 499 and sh_price == 549:
        results["Test 3 (Multi-store pricing)"] = f"PASS (FM: ₹{fm_price}, SH: ₹{sh_price})"
    else:
        results["Test 3 (Multi-store pricing)"] = f"FAIL (FM: ₹{fm_price}, SH: ₹{sh_price})"

    # -------------------------------------------------------------
    # Test 4: Stock-0 product rejection
    # -------------------------------------------------------------
    print("\n[Test 4] Stock-0 product cannot be checked out")
    coke_barcode = "8901764012296" # Stock 0 product at FM
    checkout_stock0 = client.post("/checkout", json={
        "store_id": fm_id,
        "items": [{"barcode": coke_barcode, "qty": 1}]
    })
    print(f"-> Checkout stock-0 status: {checkout_stock0.status_code}, body: {checkout_stock0.json()}")
    if checkout_stock0.status_code == 400 and "INSUFFICIENT_STOCK" in str(checkout_stock0.json()):
        results["Test 4 (Stock-0 rejection)"] = "PASS (rejected with 400 INSUFFICIENT_STOCK)"
    else:
        results["Test 4 (Stock-0 rejection)"] = f"FAIL (status: {checkout_stock0.status_code})"

    # -------------------------------------------------------------
    # Test 1: Canonical cart & Exit verification
    # -------------------------------------------------------------
    print("\n[Test 1] Canonical cart at FreshMart (Milk + Bread + Shampoo)")
    canonical_items = [
        {"barcode": "8901262010015", "qty": 1}, # Amul Milk ₹62
        {"barcode": "8901063142217", "qty": 1}, # Britannia Bread ₹45
        {"barcode": "4902430752108", "qty": 1}  # H&S Shampoo ₹210
    ]
    checkout_res = client.post("/checkout", json={
        "store_id": fm_id,
        "items": canonical_items
    })
    assert checkout_res.status_code == 200, f"Canonical checkout failed: {checkout_res.text}"
    order_data = checkout_res.json()
    order_id = order_data["order_id"]
    total = order_data["total"]
    print(f"-> Canonical cart order created: {order_id}, Total: ₹{total}")
    assert total == 317, f"Expected total 317, got {total}"
    
    # Mock pay
    pay_res = client.post(f"/orders/{order_id}/pay/mock")
    assert pay_res.status_code == 200, f"Mock pay failed: {pay_res.text}"
    bill_no = pay_res.json()["bill_no"]
    print(f"-> Order paid. Bill issued: {bill_no}")
    
    # Exit verify 1: Genuine bill
    verify1 = client.post("/exit/verify", json={"bill_no": bill_no})
    print(f"-> Exit verify genuine bill: {verify1.json()['result']}")
    assert verify1.json()["result"] == "VERIFIED", f"Expected VERIFIED, got {verify1.json()}"
    
    # Mark bill used
    use_res = client.post("/exit/use", json={"bill_no": bill_no})
    assert use_res.status_code == 200, f"Exit use failed: {use_res.text}"
    print(f"-> Bill marked USED: {use_res.json()['status']}")
    
    # Exit verify 2: Already used bill
    verify2 = client.post("/exit/verify", json={"bill_no": bill_no})
    print(f"-> Exit verify after use: {verify2.json()['result']}")
    assert verify2.json()["result"] == "ALREADY_USED", f"Expected ALREADY_USED, got {verify2.json()}"
    
    # Exit verify 3: Fake bill SS-99999
    verify_fake = client.post("/exit/verify", json={"bill_no": "SS-99999"})
    print(f"-> Exit verify fake bill SS-99999: {verify_fake.json()['result']}")
    assert verify_fake.json()["result"] == "INVALID", f"Expected INVALID, got {verify_fake.json()}"
    
    results["Test 1 (Canonical Cart & Exit verification)"] = f"PASS (Total: ₹{total}, Bill: {bill_no}, VERIFIED -> ALREADY_USED -> INVALID)"

    # -------------------------------------------------------------
    # Test 2: Double pay idempotency & single stock drop
    # -------------------------------------------------------------
    print("\n[Test 2] Double pay idempotency")
    # Check current bread stock
    sb = get_supabase()
    bread_pre = sb.table("products").select("stock").eq("store_id", fm_id).eq("barcode", "8901063142217").execute().data[0]["stock"]
    
    # Checkout 1 bread
    ck = client.post("/checkout", json={"store_id": fm_id, "items": [{"barcode": "8901063142217", "qty": 1}]})
    ck_id = ck.json()["order_id"]
    
    # First pay
    p1 = client.post(f"/orders/{ck_id}/pay/mock")
    bill1 = p1.json()["bill_no"]
    
    bread_after_p1 = sb.table("products").select("stock").eq("store_id", fm_id).eq("barcode", "8901063142217").execute().data[0]["stock"]
    
    # Second pay (double pay retry)
    p2 = client.post(f"/orders/{ck_id}/pay/mock")
    bill2 = p2.json()["bill_no"]
    
    bread_after_p2 = sb.table("products").select("stock").eq("store_id", fm_id).eq("barcode", "8901063142217").execute().data[0]["stock"]
    
    print(f"-> Bill 1: {bill1}, Bill 2: {bill2}")
    print(f"-> Bread stock: Pre={bread_pre}, After Pay 1={bread_after_p1}, After Pay 2={bread_after_p2}")
    
    if bill1 == bill2 and bread_after_p1 == bread_pre - 1 and bread_after_p2 == bread_after_p1:
        results["Test 2 (Idempotency & single stock drop)"] = f"PASS (Same bill {bill1}, stock dropped exactly 1 from {bread_pre} to {bread_after_p2})"
    else:
        results["Test 2 (Idempotency & single stock drop)"] = f"FAIL (bill1={bill1}, bill2={bill2}, stock={bread_after_p2})"

    # -------------------------------------------------------------
    # Test 5: Cash flow
    # -------------------------------------------------------------
    print("\n[Test 5] Cash flow: checkout with cash -> staff confirms -> bill activates")
    cash_ck = client.post("/checkout", json={"store_id": fm_id, "items": [{"barcode": "8904043901005", "qty": 1}]}) # Tata Salt ₹28
    cash_order_id = cash_ck.json()["order_id"]
    
    # Mark cash payment
    cash_init = client.post(f"/orders/{cash_order_id}/pay/cash")
    assert cash_init.status_code == 200
    assert cash_init.json()["payment_status"] == "CASH_PENDING"
    print(f"-> Cash order placed: {cash_order_id}, status: CASH_PENDING")
    
    # Staff confirms cash
    staff_conf = client.post(f"/orders/{cash_order_id}/confirm-cash")
    assert staff_conf.status_code == 200
    cash_bill_no = staff_conf.json()["bill_no"]
    print(f"-> Staff confirmed. Bill activated: {cash_bill_no}")
    
    # Verify exit
    cash_verify = client.post("/exit/verify", json={"bill_no": cash_bill_no})
    assert cash_verify.json()["result"] == "VERIFIED"
    print(f"-> Cash bill exit verify: {cash_verify.json()['result']}")
    results["Test 5 (Cash Flow)"] = f"PASS (Order {cash_order_id} -> CASH_PENDING -> Confirmed Bill {cash_bill_no} -> VERIFIED)"

    # -------------------------------------------------------------
    # Test 6: Manager cross-store isolation (403)
    # -------------------------------------------------------------
    print("\n[Test 6] Manager cross-store isolation (403)")
    # Mock user dependency as FM manager
    def mock_fm_manager():
        return UserProfile(id="00000000-0000-0000-0000-000000000001", email="manager@smartscan.app", role="manager", store_id=fm_id)
        
    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        # Access own store: FM
        mgr_fm = client.get(f"/manager/stores/{fm_id}/products")
        print(f"-> FM manager accessing FM products: HTTP {mgr_fm.status_code}")
        assert mgr_fm.status_code == 200
        
        # Access foreign store: SH
        mgr_sh = client.get(f"/manager/stores/{sh_id}/products")
        print(f"-> FM manager accessing SH products: HTTP {mgr_sh.status_code}")
        assert mgr_sh.status_code == 403, f"Expected 403, got {mgr_sh.status_code}"
        results["Test 6 (Manager isolation 403)"] = f"PASS (FM manager accessing SH -> 403 Forbidden)"
    finally:
        app.dependency_overrides.clear()

    print("\n" + "=" * 60)
    print("ALL ACCEPTANCE TEST RESULTS SUMMARY")
    print("=" * 60)
    for test_name, status_str in results.items():
        print(f"{test_name}: {status_str}")
    print("=" * 60)
    return results

if __name__ == "__main__":
    run_acceptance_tests()
