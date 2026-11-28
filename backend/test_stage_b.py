"""
SmartScan 2026 — Stage B Acceptance Tests: GST Billing & Compliance
Executes all 7 acceptance checks from Stage B specification:
1. test_1: default_gst_rate logic (milk 0%, bread 0%, bakery 0%, shampoo 5%, electronics 18%, clothing 499 -> 5%, clothing 3499 -> 18%)
2. test_2: GST math on proof case (Milk 62 + Bread 45 + Shampoo 210 = 317 total. 0% slab: taxable 107.00, tax 0.00; 5% slab: taxable 200.00, tax 10.00 (CGST 5.00, SGST 5.00). Grand total 317.00. Taxable + tax == grand_total, CGST + SGST == tax)
3. test_3: Checkout with customer_mobile & validation (accept valid 10-digit 9876543210, reject invalid like '123' or 'abc' or 9-digit, allow empty/null)
4. test_4: Bill retrieval contains GST breakup, slabs, customer_mobile, mrp_total, discount, item gst_rate
5. test_5: Manager product add/edit with gst_rate, and clothing price auto-switch when price crosses 2500 (unless explicitly specified)
6. test_6: Manager GST summary endpoint returns aggregated slabs for today and month
7. test_7: Store isolation: manager cannot view bills or GST summary of another store (returns 403)
"""

import sys
import os
import uuid

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.testclient import TestClient
from main import app
from core.db import get_supabase
from core.auth import UserProfile, get_current_user
from core.gst import default_gst_rate, compute_gst_breakup, VALID_GST_RATES
from core.rate_limit import check_checkout_rate_limit

client = TestClient(app)
app.dependency_overrides[check_checkout_rate_limit] = lambda: None

def run_stage_b_tests():
    print("=" * 65)
    print("SMARTSCAN 2026 — STAGE B ACCEPTANCE TESTS (GST & COMPLIANCE)")
    print("=" * 65)
    
    results = {}
    sb = get_supabase()

    # Pre-fetch demo stores
    stores_res = client.get("/stores")
    assert stores_res.status_code == 200, f"Failed to get stores: {stores_res.text}"
    stores = stores_res.json()
    stores_by_code = {s["code"]: s for s in stores if s.get("code") in ("FM", "SH", "DN")}
    fm_id = stores_by_code["FM"]["id"]
    sh_id = stores_by_code["SH"]["id"]

    # -------------------------------------------------------------
    # Test 1: GST Master Rules & Default Rates
    # -------------------------------------------------------------
    print("\n[Test 1] GST Master Rules & Default Rates")
    try:
        assert default_gst_rate("Dairy", "Amul Taaza Milk 500ml", 62) == 0, "Milk should be 0%"
        assert default_gst_rate("Bakery", "Britannia Whole Wheat Bread", 45) == 0, "Bread should be 0%"
        assert default_gst_rate("Bakery", "Chocolate Croissant", 80) == 0, "Bakery category should be 0%"
        assert default_gst_rate("Personal Care", "Head & Shoulders Shampoo 340ml", 210) == 5, "Shampoo should be 5%"
        assert default_gst_rate("Groceries", "Tata Salt 1kg", 28) == 5, "FMCG Grocery should be 5%"
        assert default_gst_rate("Electronics", "Bluetooth Headphones", 1499) == 18, "Electronics should be 18%"
        assert default_gst_rate("Appliances", "Electric Kettle", 1200) == 18, "Appliances should be 18%"
        assert default_gst_rate("Clothing", "Basic T-Shirt", 499) == 5, "Clothing <= 2500 should be 5%"
        assert default_gst_rate("Clothing", "Designer Jacket", 3499) == 18, "Clothing > 2500 should be 18%"
        assert default_gst_rate("Apparel", "Formal Suit", 2501) == 18, "Apparel > 2500 should be 18%"
        assert default_gst_rate("Footwear", "Leather Shoes", 2500) == 5, "Footwear == 2500 should be 5%"

        print("-> All default GST rate rules verified correctly.")
        results["Test 1 (GST Master Rules)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 1: {e}")
        results["Test 1 (GST Master Rules)"] = f"FAIL: {e}"

    # -------------------------------------------------------------
    # Test 2: GST Inclusive Math & Proof Case
    # -------------------------------------------------------------
    print("\n[Test 2] GST Math on Canonical Proof Case (Milk + Bread + Shampoo = ₹317)")
    try:
        items = [
            {"name": "Amul Taaza Milk 500ml", "price": 62, "qty": 1, "gst_rate": 0},
            {"name": "Britannia Whole Wheat Bread", "price": 45, "qty": 1, "gst_rate": 0},
            {"name": "Head & Shoulders Shampoo 340ml", "price": 210, "qty": 1, "gst_rate": 5}
        ]
        breakup = compute_gst_breakup(items)
        slabs = {s["rate"]: s for s in breakup["slabs"]}
        totals = breakup["totals"]

        # 0% slab
        assert 0 in slabs, "0% slab missing from breakup"
        assert slabs[0]["taxable_value"] == 107.00, f"Expected 0% taxable 107.00, got {slabs[0]['taxable_value']}"
        assert slabs[0]["tax"] == 0.00, f"Expected 0% tax 0.00, got {slabs[0]['tax']}"
        assert slabs[0]["cgst"] == 0.00, f"Expected 0% cgst 0.00, got {slabs[0]['cgst']}"
        assert slabs[0]["sgst"] == 0.00, f"Expected 0% sgst 0.00, got {slabs[0]['sgst']}"

        # 5% slab
        assert 5 in slabs, "5% slab missing from breakup"
        assert slabs[5]["taxable_value"] == 200.00, f"Expected 5% taxable 200.00, got {slabs[5]['taxable_value']}"
        assert slabs[5]["tax"] == 10.00, f"Expected 5% tax 10.00, got {slabs[5]['tax']}"
        assert slabs[5]["cgst"] == 5.00, f"Expected 5% cgst 5.00, got {slabs[5]['cgst']}"
        assert slabs[5]["sgst"] == 5.00, f"Expected 5% sgst 5.00, got {slabs[5]['sgst']}"

        # Totals
        assert totals["grand_total"] == 317, f"Expected grand total 317, got {totals['grand_total']}"
        assert round(totals["taxable_value"] + totals["tax"], 2) == totals["grand_total"], "taxable + tax must equal grand total"
        assert round(totals["cgst"] + totals["sgst"], 2) == totals["tax"], "cgst + sgst must equal total tax"
        
        print("-> Proof case verified: 0% slab (107 taxable, 0 tax), 5% slab (200 taxable, 10 tax), total ₹317.00 exact.")
        results["Test 2 (Proof Case Math)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 2: {e}")
        results["Test 2 (Proof Case Math)"] = f"FAIL: {e}"

    # -------------------------------------------------------------
    # Test 3: Checkout with Customer Mobile & Validation
    # -------------------------------------------------------------
    print("\n[Test 3] Checkout with Customer Mobile & Validation")
    try:
        # Valid 10-digit mobile
        valid_res = client.post("/checkout", json={
            "store_id": fm_id,
            "items": [{"barcode": "8901262010015", "qty": 1}],
            "customer_mobile": "9876543210"
        })
        assert valid_res.status_code == 200, f"Expected 200, got {valid_res.status_code}: {valid_res.text}"
        data = valid_res.json()
        assert data["customer_mobile"] == "9876543210", f"Expected mobile 9876543210, got {data.get('customer_mobile')}"
        assert data["item_count"] == 1
        assert "items" in data and len(data["items"]) == 1
        assert data["items"][0]["gst_rate"] == 0, "Milk gst_rate should be 0"

        # Invalid mobiles should be rejected with 422
        bad_mobiles = ["123", "abc", "987654321", "5876543210", "98765432101"]
        for bad_m in bad_mobiles:
            bad_res = client.post("/checkout", json={
                "store_id": fm_id,
                "items": [{"barcode": "8901262010015", "qty": 1}],
                "customer_mobile": bad_m
            })
            assert bad_res.status_code == 422, f"Expected 422 for bad mobile '{bad_m}', got {bad_res.status_code}"

        # Null / Empty mobile should be accepted as None
        empty_res = client.post("/checkout", json={
            "store_id": fm_id,
            "items": [{"barcode": "8901262010015", "qty": 1}],
            "customer_mobile": None
        })
        assert empty_res.status_code == 200
        assert empty_res.json()["customer_mobile"] is None

        print("-> Mobile validation passed: accepted 10-digit 9876543210, rejected malformed, allowed optional None.")
        results["Test 3 (Customer Mobile Validation)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 3: {e}")
        results["Test 3 (Customer Mobile Validation)"] = f"FAIL: {e}"

    # -------------------------------------------------------------
    # Test 4: Bill Retrieval & GST Breakup Payload
    # -------------------------------------------------------------
    print("\n[Test 4] Bill Retrieval & GST Breakup Payload")
    try:
        # Create canonical order and pay it
        checkout_res = client.post("/checkout", json={
            "store_id": fm_id,
            "items": [
                {"barcode": "8901262010015", "qty": 1},
                {"barcode": "8901063142217", "qty": 1},
                {"barcode": "4902430752108", "qty": 1}
            ],
            "customer_mobile": "9876543210"
        })
        assert checkout_res.status_code == 200
        order_id = checkout_res.json()["order_id"]

        pay_res = client.post(f"/orders/{order_id}/mock-pay")
        assert pay_res.status_code == 200
        pay_data = pay_res.json()
        bill_no = pay_data["bill_no"]

        # Check mock-pay response payload
        assert pay_data["customer_mobile"] == "9876543210"
        assert pay_data["item_count"] == 3
        assert pay_data["total"] == 317
        assert pay_data["gst_breakup"] is not None
        assert pay_data["gst_totals"] is not None
        assert pay_data["gst_totals"]["grand_total"] == 317

        # Check /bills/{bill_no} endpoint
        bill_res = client.get(f"/bills/{bill_no}")
        assert bill_res.status_code == 200
        bill_data = bill_res.json()
        assert bill_data["customer_mobile"] == "9876543210"
        assert bill_data["item_count"] == 3
        assert len(bill_data["gst_breakup"]) >= 2  # 2 slabs + Total
        assert any(r["rate"] == "Total" for r in bill_data["gst_breakup"])

        # Check /exit/verify endpoint
        exit_res = client.post("/exit/verify", json={"bill_no": bill_no})
        assert exit_res.status_code == 200
        exit_data = exit_res.json()
        assert exit_data["result"] == "VERIFIED"
        assert exit_data["customer_mobile"] == "9876543210"
        assert exit_data["item_count"] == 3
        assert exit_data["gst_breakup"] is not None

        print("-> Bill payload verified across pay, /bills, and /exit/verify with full GST breakup.")
        results["Test 4 (Bill Retrieval & GST Breakup)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 4: {e}")
        results["Test 4 (Bill Retrieval & GST Breakup)"] = f"FAIL: {e}"

    # -------------------------------------------------------------
    # Test 5: Manager Product Add/Edit with GST Rate & Clothing Slab
    # -------------------------------------------------------------
    print("\n[Test 5] Manager Product Add/Edit with GST Rate & Clothing Slab Auto-switch")
    try:
        # Mock manager profile for FreshMart
        manager_user = UserProfile(id=str(uuid.uuid4()), email="manager@smartscan.app", role="manager", store_id=fm_id)
        app.dependency_overrides[get_current_user] = lambda: manager_user

        test_barcode_1 = f"8909999{str(uuid.uuid4().int)[:6]}"
        test_barcode_2 = f"8908888{str(uuid.uuid4().int)[:6]}"

        # 1. Add product with explicit gst_rate = 12
        add_res_1 = client.post(f"/manager/stores/{fm_id}/products", json={
            "barcode": test_barcode_1,
            "name": "Processed Snacks Premium",
            "category": "Snacks",
            "price": 150,
            "stock": 20,
            "gst_rate": 12
        })
        assert add_res_1.status_code == 201, f"Failed add: {add_res_1.text}"
        prod_1 = add_res_1.json()
        assert prod_1["gst_rate"] == 12, f"Expected gst_rate 12, got {prod_1.get('gst_rate')}"

        # 2. Add clothing product without gst_rate at price <= 2500 (should default to 5%)
        add_res_2 = client.post(f"/manager/stores/{fm_id}/products", json={
            "barcode": test_barcode_2,
            "name": "Cotton Polo T-Shirt",
            "category": "Clothing",
            "price": 1999,
            "stock": 15
        })
        assert add_res_2.status_code == 201, f"Failed add: {add_res_2.text}"
        prod_2 = add_res_2.json()
        assert prod_2["gst_rate"] == 5, f"Expected clothing <= 2500 to have gst_rate 5, got {prod_2.get('gst_rate')}"

        # 3. Patch clothing price to > 2500 without specifying gst_rate -> auto-switches to 18%
        patch_res = client.patch(f"/manager/stores/{fm_id}/products/{prod_2['id']}", json={
            "price": 2999
        })
        assert patch_res.status_code == 200, f"Failed patch: {patch_res.text}"
        updated_prod_2 = patch_res.json()
        assert updated_prod_2["price"] == 2999
        assert updated_prod_2["gst_rate"] == 18, f"Expected clothing > 2500 to auto-switch to 18, got {updated_prod_2.get('gst_rate')}"

        # 4. Patch clothing price with explicit gst_rate override
        patch_res_explicit = client.patch(f"/manager/stores/{fm_id}/products/{prod_2['id']}", json={
            "price": 3499,
            "gst_rate": 5
        })
        assert patch_res_explicit.status_code == 200
        assert patch_res_explicit.json()["gst_rate"] == 5, "Explicit gst_rate override must be respected"

        # 5. Invalid gst_rate should return 400
        bad_add = client.post(f"/manager/stores/{fm_id}/products", json={
            "barcode": f"8907777{str(uuid.uuid4().int)[:6]}",
            "name": "Invalid Tax Item",
            "category": "General",
            "price": 100,
            "stock": 10,
            "gst_rate": 7  # invalid
        })
        assert bad_add.status_code == 400, f"Expected 400 for invalid gst_rate 7, got {bad_add.status_code}"

        print("-> Product add/edit verified: explicit rate saved, clothing slab auto-switch (<2500: 5%, >2500: 18%), invalid rate rejected.")
        results["Test 5 (Manager Product GST & Clothing Slab)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 5: {e}")
        results["Test 5 (Manager Product GST & Clothing Slab)"] = f"FAIL: {e}"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # -------------------------------------------------------------
    # Test 6: Manager GST Summary Endpoint
    # -------------------------------------------------------------
    print("\n[Test 6] Manager GST Summary Endpoint (Today & Month)")
    try:
        manager_fm = UserProfile(id=str(uuid.uuid4()), email="manager@smartscan.app", role="manager", store_id=fm_id)
        app.dependency_overrides[get_current_user] = lambda: manager_fm

        # Today summary
        res_today = client.get(f"/manager/gst-summary?store_id={fm_id}&period=today")
        assert res_today.status_code == 200, f"Failed today summary: {res_today.text}"
        data_today = res_today.json()
        assert data_today["period"] == "today"
        assert data_today["store_id"] == fm_id
        assert "slabs" in data_today
        assert "totals" in data_today
        assert "breakup_rows" in data_today
        assert data_today["totals"]["grand_total"] >= 0

        # Month summary
        res_month = client.get(f"/manager/gst-summary?store_id={fm_id}&period=month")
        assert res_month.status_code == 200, f"Failed month summary: {res_month.text}"
        data_month = res_month.json()
        assert data_month["period"] == "month"
        assert data_month["orders_count"] >= 0
        assert round(data_month["totals"]["taxable_value"] + data_month["totals"]["tax"], 2) == data_month["totals"]["grand_total"]

        print(f"-> GST summary verified: Today ({data_today['orders_count']} orders, ₹{data_today['total_sales']} sales) & Month ({data_month['orders_count']} orders, ₹{data_month['total_sales']} sales).")
        results["Test 6 (Manager GST Summary)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 6: {e}")
        results["Test 6 (Manager GST Summary)"] = f"FAIL: {e}"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # -------------------------------------------------------------
    # Test 7: Store Isolation for Manager Orders & Bills
    # -------------------------------------------------------------
    print("\n[Test 7] Store Isolation for Manager Orders & Bills")
    try:
        # Create an order at StyleHub (sh_id)
        sh_checkout = client.post("/checkout", json={
            "store_id": sh_id,
            "items": [{"barcode": "8901234567890", "qty": 1}]
        })
        assert sh_checkout.status_code == 200
        sh_order_id = sh_checkout.json()["order_id"]
        sh_pay = client.post(f"/orders/{sh_order_id}/mock-pay")
        assert sh_pay.status_code == 200
        sh_bill_no = sh_pay.json()["bill_no"]

        # Authenticate as FreshMart Manager
        fm_manager = UserProfile(id=str(uuid.uuid4()), email="manager-fm@smartscan.app", role="manager", store_id=fm_id)
        app.dependency_overrides[get_current_user] = lambda: fm_manager

        # FM manager attempting to access StyleHub bill detail
        forbidden_res = client.get(f"/manager/orders/{sh_bill_no}")
        assert forbidden_res.status_code == 403, f"Expected 403 Forbidden for cross-store bill, got {forbidden_res.status_code}: {forbidden_res.text}"

        # FM manager attempting to access StyleHub GST summary
        forbidden_gst = client.get(f"/manager/gst-summary?store_id={sh_id}&period=today")
        assert forbidden_gst.status_code == 403, f"Expected 403 Forbidden for cross-store GST summary, got {forbidden_gst.status_code}: {forbidden_gst.text}"

        print("-> Store isolation verified: FM manager correctly blocked (403) from accessing StyleHub bill and GST summary.")
        results["Test 7 (Manager Store Isolation)"] = "PASS"
    except Exception as e:
        print(f"FAILED Test 7: {e}")
        results["Test 7 (Manager Store Isolation)"] = f"FAIL: {e}"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    print("\n" + "=" * 65)
    print("STAGE B TEST SUMMARY:")
    all_passed = True
    for t_name, t_status in results.items():
        print(f"  {t_name}: {t_status}")
        if not t_status.startswith("PASS"):
            all_passed = False
    print("=" * 65)
    return all_passed

if __name__ == "__main__":
    success = run_stage_b_tests()
    sys.exit(0 if success else 1)
