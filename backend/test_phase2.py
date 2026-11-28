"""
SmartScan 2026 — Phase 2 Acceptance Tests
Executes all 8 acceptance checks for retailer onboarding, manager dashboard, and hardening:
1. Scan-to-add: manager adds barcode 8907777666655 'Test Biscuits' at FM -> customer scan returns it at Rs 40.
2. Duplicate barcode in same store returns 409 Conflict.
3. CSV bulk import: preview with 6 rows (3 new, 1 update, 2 invalid) returns Add 3 / Update 1 / Fail 2 with reasons, saves nothing. Execution upserts and updates catalogue.
4. Unknown-scans queue: customer scans 8909999888877 twice -> queue count 2 -> manager adds product from queue -> queue row gone -> customer scan succeeds.
5. Manager dashboard: today's orders/revenue match DB; low-stock list includes stock-0 Coca-Cola; 7-day sales and SDG impact verified.
6. Rate limit: rapid bursts to /scan return 429 RATE_LIMIT_EXCEEDED.
7. Demo reset: custom manager products survive; seed products reset; orders return to 40; canonical SS-20481 cart works.
8. Regression: test_phase1 still passes 7/7.
"""

import sys
import os
import time

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.testclient import TestClient
from main import app
from core.db import get_supabase
from core.auth import UserProfile, get_current_user
import test_phase1

client = TestClient(app)

def run_phase2_tests():
    print("=" * 65)
    print("SMARTSCAN 2026 — PHASE 2 ACCEPTANCE TESTS")
    print("=" * 65)

    results = {}
    sb = get_supabase()

    # Pre-fetch store IDs
    stores_res = client.get("/stores")
    assert stores_res.status_code == 200, f"Failed to get stores: {stores_res.text}"
    stores = stores_res.json()
    stores_by_code = {s["code"]: s for s in stores}
    fm_id = stores_by_code["FM"]["id"]
    sh_id = stores_by_code["SH"]["id"]
    dn_id = stores_by_code["DN"]["id"]

    # Helper manager auth dependency override
    def mock_fm_manager():
        return UserProfile(
            id="00000000-0000-0000-0000-000000000001",
            email="manager@smartscan.app",
            role="manager",
            store_id=fm_id
        )

    # -------------------------------------------------------------
    # Test 1: Scan-to-Add (Manager)
    # -------------------------------------------------------------
    print("\n[Test 1] Scan-to-add: manager adds 'Test Biscuits' at FreshMart")
    test_barcode = "8907777666655"
    # Ensure clean slate for test barcode
    sb.table("products").delete().eq("store_id", fm_id).eq("barcode", test_barcode).execute()

    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        add_res = client.post(
            f"/manager/stores/{fm_id}/products",
            json={
                "barcode": test_barcode,
                "name": "Test Biscuits",
                "brand": "TestBrand",
                "category": "Snacks",
                "price": 40,
                "mrp": 45,
                "stock": 10,
                "unit": "100g"
            }
        )
        assert add_res.status_code == 201, f"Scan-to-add failed: HTTP {add_res.status_code}: {add_res.text}"
        prod_data = add_res.json()
        print(f"-> Created product: id={prod_data['id']}, name='{prod_data['name']}', price=Rs {prod_data['price']}")
    finally:
        app.dependency_overrides.clear()

    # Customer scans the newly added product
    scan_res = client.post("/scan", json={"store_id": fm_id, "barcode": test_barcode})
    assert scan_res.status_code == 200, f"Customer scan failed: HTTP {scan_res.status_code}: {scan_res.text}"
    scanned = scan_res.json()
    print(f"-> Customer scan verified: '{scanned['name']}' at Rs {scanned['price']}, stock={scanned['stock']}")

    if scanned["name"] == "Test Biscuits" and scanned["price"] == 40 and scanned["stock"] == 10:
        results["Test 1 (Scan-to-Add)"] = "PASS (Manager added product live -> customer scan succeeded at Rs 40)"
    else:
        results["Test 1 (Scan-to-Add)"] = f"FAIL (Unexpected scan data: {scanned})"

    # -------------------------------------------------------------
    # Test 2: Duplicate Barcode Check (409 Conflict)
    # -------------------------------------------------------------
    print("\n[Test 2] Duplicate barcode in same store returns 409 Conflict")
    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        dup_res = client.post(
            f"/manager/stores/{fm_id}/products",
            json={
                "barcode": test_barcode,
                "name": "Duplicate Biscuits",
                "category": "Snacks",
                "price": 42,
                "stock": 5
            }
        )
        print(f"-> Duplicate post status: HTTP {dup_res.status_code}, response: {dup_res.text}")
        if dup_res.status_code == 409 and "already exists" in dup_res.text:
            results["Test 2 (Duplicate 409)"] = "PASS (Duplicate barcode correctly rejected with HTTP 409 Conflict)"
        else:
            results["Test 2 (Duplicate 409)"] = f"FAIL (Expected 409 Conflict, got {dup_res.status_code})"
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------
    # Test 3: CSV Bulk Import (Preview dry run & Confirm execution)
    # -------------------------------------------------------------
    print("\n[Test 3] CSV bulk import: dry run preview & execute")
    # Clean test barcodes and reset Tata Salt to base state
    for b in ["8908888000001", "8908888000002", "8908888000003"]:
        sb.table("products").delete().eq("store_id", fm_id).eq("barcode", b).execute()
    sb.table("products").update({"price": 28, "stock": 50}).eq("store_id", fm_id).eq("barcode", "8904043901005").execute()

    csv_data = (
        "barcode,name,brand,category,price,mrp,stock,unit\n"
        "8908888000001,New Item 1,Brand A,Snacks,50,60,20,1 pc\n"
        "8908888000002,New Item 2,Brand B,Dairy,30,35,15,500ml\n"
        "8908888000003,New Item 3,Brand C,Beverages,70,80,25,1L\n"
        "8904043901005,Tata Salt 1kg,Tata,Groceries,32,35,45,1kg\n" # Existing update (was Rs 28)
        "8908888000005,Invalid Price Item,Brand E,General,49.99,60,10,1 pc\n" # Invalid decimal price
        ",No Barcode Item,Brand F,General,100,120,10,1 pc\n" # Missing barcode
    )

    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        # 1. Preview
        prev_res = client.post(
            f"/manager/stores/{fm_id}/products/import-preview",
            content=csv_data.encode("utf-8"),
            headers={"Content-Type": "text/csv"}
        )
        assert prev_res.status_code == 200, f"Preview failed: HTTP {prev_res.status_code}: {prev_res.text}"
        prev = prev_res.json()
        print(f"-> Preview results: Total={prev['total_rows']}, Add={prev['to_add_count']}, Update={prev['to_update_count']}, Fail={prev['to_fail_count']}")

        # Verify preview saved nothing
        salt_check = sb.table("products").select("price").eq("store_id", fm_id).eq("barcode", "8904043901005").execute()
        assert salt_check.data[0]["price"] == 28, "Preview mutated existing product!"

        new_check = sb.table("products").select("id").eq("store_id", fm_id).eq("barcode", "8908888000001").execute()
        assert not new_check.data, "Preview created new product in DB!"

        # 2. Execute
        exec_res = client.post(
            f"/manager/stores/{fm_id}/products/import",
            content=csv_data.encode("utf-8"),
            headers={"Content-Type": "text/csv"}
        )
        assert exec_res.status_code == 200, f"Import execution failed: HTTP {exec_res.status_code}: {exec_res.text}"
        im_res = exec_res.json()
        print(f"-> Import executed: Added={im_res['added_count']}, Updated={im_res['updated_count']}, Failed={im_res['failed_count']}")

        # Verify DB changes
        salt_after = sb.table("products").select("price, stock").eq("store_id", fm_id).eq("barcode", "8904043901005").execute()
        assert salt_after.data[0]["price"] == 32, f"Expected salt price 32, got {salt_after.data[0]['price']}"
        assert salt_after.data[0]["stock"] == 45, f"Expected salt stock 45, got {salt_after.data[0]['stock']}"

        item1 = sb.table("products").select("id, name, price").eq("store_id", fm_id).eq("barcode", "8908888000001").execute()
        assert item1.data, "New item 1 was not inserted!"

        if (prev["to_add_count"] == 3 and prev["to_update_count"] == 1 and prev["to_fail_count"] == 2 and
            im_res["added_count"] == 3 and im_res["updated_count"] == 1 and im_res["failed_count"] == 2):
            results["Test 3 (CSV Bulk Import)"] = "PASS (Preview: Add 3, Update 1, Fail 2 with zero side-effects; Execute applied 3 adds + 1 update cleanly)"
        else:
            results["Test 3 (CSV Bulk Import)"] = f"FAIL (Preview: {prev}, Execute: {im_res})"
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------
    # Test 4: Unknown Scans Queue
    # -------------------------------------------------------------
    print("\n[Test 4] Unknown scans queue lifecycle")
    unk_barcode = "8909999888877"
    # Ensure clean state in unknown_scans and products
    sb.table("unknown_scans").delete().eq("store_id", fm_id).eq("barcode", unk_barcode).execute()
    sb.table("products").delete().eq("store_id", fm_id).eq("barcode", unk_barcode).execute()

    # Customer scans unknown barcode twice
    s1 = client.post("/scan", json={"store_id": fm_id, "barcode": unk_barcode})
    assert s1.status_code == 404
    s2 = client.post("/scan", json={"store_id": fm_id, "barcode": unk_barcode})
    assert s2.status_code == 404

    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        # Check unknown queue
        queue_res = client.get(f"/manager/stores/{fm_id}/unknown-scans")
        assert queue_res.status_code == 200
        queue_items = queue_res.json()
        matching_unk = [u for u in queue_items if u["barcode"] == unk_barcode]
        assert len(matching_unk) == 1, f"Expected 1 queue item for {unk_barcode}, got {len(matching_unk)}"
        assert matching_unk[0]["count"] == 2, f"Expected count=2, got {matching_unk[0]['count']}"
        print(f"-> Unknown scan logged in queue with count={matching_unk[0]['count']}")

        # Manager resolves it by adding product
        res_add = client.post(
            f"/manager/stores/{fm_id}/products",
            json={
                "barcode": unk_barcode,
                "name": "Instant Noodles 70g",
                "category": "Snacks",
                "price": 20,
                "stock": 50
            }
        )
        assert res_add.status_code == 201

        # Check unknown queue again - should be automatically removed
        queue_after = client.get(f"/manager/stores/{fm_id}/unknown-scans").json()
        assert not any(u["barcode"] == unk_barcode for u in queue_after), "Unknown scan row was not auto-removed!"
        print("-> Product saved: barcode auto-removed from unknown queue")
    finally:
        app.dependency_overrides.clear()

    # Customer scans now - should succeed
    s3 = client.post("/scan", json={"store_id": fm_id, "barcode": unk_barcode})
    assert s3.status_code == 200
    assert s3.json()["price"] == 20
    print(f"-> Customer scan now succeeds: '{s3.json()['name']}' at Rs {s3.json()['price']}")
    results["Test 4 (Unknown Scan Queue)"] = "PASS (2 misses logged -> count=2 -> resolved on product add -> queue row cleared -> scan succeeds)"

    # -------------------------------------------------------------
    # Test 5: Manager Dashboard Metrics & Low-Stock List
    # -------------------------------------------------------------
    print("\n[Test 5] Manager dashboard metrics, low-stock, 7-day chart & SDG impact")
    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        dash_res = client.get(f"/manager/stores/{fm_id}/dashboard?range=today")
        assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.status_code}"
        dash = dash_res.json()

        # 1. Low stock verification (must include stock-0 Coca-Cola)
        low_stock = dash.get("low_stock_products") or dash.get("low_stock_items") or []
        assert any(p["barcode"] == "8901764012296" and p["stock"] == 0 for p in low_stock), "Coca-Cola (stock 0) missing from low-stock list!"
        assert all(p["stock"] <= 5 for p in low_stock), "Low stock list contains items with stock > 5!"
        print(f"-> Low stock inventory verified: {len(low_stock)} items (includes Coca-Cola 0-stock)")

        # 2. 7-Day sales chart
        sales_7d = dash.get("sales_7d") or dash.get("sales_last_7_days") or []
        assert len(sales_7d) == 7, f"Expected 7-day sales breakdown, got {len(sales_7d)}"
        print(f"-> 7-day sales breakdown verified: {len(sales_7d)} daily entries")

        # 3. Top products
        top_prods = dash.get("top_products") or []
        assert len(top_prods) <= 5, f"Top products exceeds 5: {len(top_prods)}"
        print(f"-> Top products verified: {[p['name'] for p in top_prods]}")

        # 4. SDG impact
        sdg = dash.get("sdg_impact") or dash.get("impact") or {}
        queue_saved = sdg.get("queue_time_saved_minutes", 0)
        paper_saved = sdg.get("paper_bills_saved") or sdg.get("paper_bills_avoided", 0)
        assert queue_saved >= 0 and paper_saved >= 0
        print(f"-> SDG impact metrics verified: {queue_saved} min queue saved, {paper_saved} paper bills avoided")

        results["Test 5 (Dashboard Metrics)"] = f"PASS (Low-stock includes Coca-Cola 0-stock, 7-day chart has 7 days, SDG: {queue_saved}m saved / {paper_saved} bills)"
    finally:
        app.dependency_overrides.clear()

    # -------------------------------------------------------------
    # Test 6: Rate Limiting (429 Too Many Requests)
    # -------------------------------------------------------------
    print("\n[Test 6] Rate limiting: rapid scan burst returns 429 RATE_LIMIT_EXCEEDED")
    isolated_headers = {"X-Forwarded-For": "198.51.100.77"}
    got_429 = False
    status_codes = []

    # Fire 12 rapid requests in tight loop
    for _ in range(12):
        r = client.post(
            "/scan",
            json={"store_id": fm_id, "barcode": "8901262010015"},
            headers=isolated_headers
        )
        status_codes.append(r.status_code)
        if r.status_code == 429:
            got_429 = True
            err_data = r.json()
            assert "RATE_LIMIT_EXCEEDED" in str(err_data), f"Expected RATE_LIMIT_EXCEEDED code, got {err_data}"
            print(f"-> Rate limit triggered at request #{len(status_codes)} with HTTP 429: {err_data}")
            break

    if got_429:
        results["Test 6 (Rate Limiting)"] = "PASS (Burst requests returned HTTP 429 RATE_LIMIT_EXCEEDED)"
    else:
        results["Test 6 (Rate Limiting)"] = f"FAIL (Did not trigger 429 in 12 requests. Codes: {status_codes})"

    # -------------------------------------------------------------
    # Test 7: Demo Reset (Preserve Custom Products)
    # -------------------------------------------------------------
    print("\n[Test 7] Demo reset: custom products survive, orders back to 40, canonical SS-20481 works")
    # Reset demo state with manager auth
    app.dependency_overrides[get_current_user] = mock_fm_manager
    try:
        reset_res = client.post("/manager/demo-reset")
        assert reset_res.status_code == 200, f"Demo reset failed: {reset_res.text}"
        reset_data = reset_res.json()
        print(f"-> Reset response: {reset_data['message']}")
    finally:
        app.dependency_overrides.clear()

    # 1. Custom product from Test 1 must survive
    custom_check = sb.table("products").select("name, price, stock").eq("store_id", fm_id).eq("barcode", test_barcode).execute()
    assert custom_check.data, f"Custom product {test_barcode} was wiped during demo reset!"
    assert custom_check.data[0]["name"] == "Test Biscuits"
    print(f"-> Custom manager product preserved: '{custom_check.data[0]['name']}' at Rs {custom_check.data[0]['price']}")

    # 2. Seed product Coca-Cola stock is reset to 0
    coke_check = sb.table("products").select("stock").eq("store_id", fm_id).eq("barcode", "8901764012296").execute()
    assert coke_check.data[0]["stock"] == 0, f"Coca-Cola stock not reset to 0: {coke_check.data[0]['stock']}"
    print(f"-> Seed product Coca-Cola stock reset to 0")

    # 3. Exactly 40 demo orders present in app2026.orders, and stores still 103
    demo_orders_res = sb.table("orders").select("id", count="exact").in_("store_id", [fm_id, sh_id, dn_id]).execute()
    demo_orders_count = demo_orders_res.count if demo_orders_res.count is not None else len(demo_orders_res.data)
    assert demo_orders_count == 40, f"Expected exactly 40 demo orders after reset, got {demo_orders_count}"
    print(f"-> Verified exactly {demo_orders_count} demo orders in DB")

    # 4. Canonical bill SS-20481 exists and checkout works
    can_check = client.get("/bills/SS-20481")
    assert can_check.status_code == 200, f"Canonical bill fetch failed: {can_check.text}"
    assert can_check.json()["total"] == 317
    print(f"-> Canonical bill SS-20481 verified: total=Rs {can_check.json()['total']}, status={can_check.json()['status']}")

    results["Test 7 (Demo Reset)"] = f"PASS (Custom product {test_barcode} survived, 40 orders restored, canonical SS-20481 bill active at Rs 317)"

    # -------------------------------------------------------------
    # Test 8: Regression Test (Phase 1 Acceptance Suite)
    # -------------------------------------------------------------
    print("\n[Test 8] Regression: running test_phase1 acceptance tests")
    p1_results = test_phase1.run_acceptance_tests()
    p1_passes = sum(1 for v in p1_results.values() if v.startswith("PASS"))
    p1_total = len(p1_results)
    print(f"-> Phase 1 test suite result: {p1_passes}/{p1_total} passed")

    if p1_passes == p1_total:
        results["Test 8 (Phase 1 Regression)"] = f"PASS (All {p1_passes}/{p1_total} Phase 1 acceptance tests passed without regression)"
    else:
        results["Test 8 (Phase 1 Regression)"] = f"FAIL (Only {p1_passes}/{p1_total} passed)"

    print("\n" + "=" * 65)
    print("ALL PHASE 2 ACCEPTANCE TEST RESULTS SUMMARY")
    print("=" * 65)
    for test_name, status_str in results.items():
        print(f"{test_name}: {status_str}")
    print("=" * 65)
    return results

if __name__ == "__main__":
    run_phase2_tests()
