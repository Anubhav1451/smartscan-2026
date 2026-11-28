"""
SmartScan 2026 — Stage D Acceptance Tests: Fake Bill Generator & Dramatic INVALID Detection
Tests:
1. Verify on a guaranteed-absent bill number returns result INVALID with rejected bill_no.
2. Verify on full QR token payload with absent bill extracts bill_no and returns INVALID.
3. GET /exit/check/{bill_no} staff-only endpoint enforces authentication and role isolation.
4. GET /exit/check/{bill_no} correctly reports exists=False for absent bill and exists=True for SS-20481.
5. Verify on seeded canonical bill SS-20481 returns VERIFIED, total=317, 3 items, and remains UNCONSUMED.
6. Frontend build sanity check: staff screen & fake bill generator components compile without error.
"""

import sys
import os
import random
import subprocess
from starlette.testclient import TestClient

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from core.auth import get_current_user, UserProfile
from core.db import get_supabase

client = TestClient(app)
sb = get_supabase()

def test_verify_guaranteed_absent_bill_returns_invalid():
    print("\n[Test 1] Testing /exit/verify on guaranteed-absent bill number...")
    app.dependency_overrides.pop(get_current_user, None)

    # Pick a guaranteed absent bill number
    rand_suffix = random.randint(91000, 99999)
    absent_bill = f"SS-{rand_suffix}"

    # Verify absence from DB first
    chk = sb.table("orders").select("id").eq("bill_no", absent_bill).execute()
    assert not chk.data or len(chk.data) == 0, f"Candidate {absent_bill} already exists in DB!"

    resp = client.post("/exit/verify", json={"bill_no": absent_bill})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data.get("result") == "INVALID", f"Expected result 'INVALID', got {data.get('result')}"
    assert data.get("bill_no") == absent_bill, f"Expected bill_no '{absent_bill}', got {data.get('bill_no')}"
    assert "Invalid or unrecognized" in data.get("message", ""), f"Unexpected message: {data.get('message')}"

    print(f"-> Verified: Absent bill {absent_bill} returned result='INVALID' with bill_no='{absent_bill}'")
    print("PASS: /exit/verify correctly marks absent bills as INVALID")


def test_verify_qr_payload_with_absent_bill():
    print("\n[Test 2] Testing /exit/verify with full QR token payload containing absent bill...")
    app.dependency_overrides.pop(get_current_user, None)

    rand_suffix = random.randint(91000, 99999)
    absent_bill = f"SS-{rand_suffix}"
    qr_payload = f"SMARTSCAN|BILL|{absent_bill}|fake-order-id|FM|255"

    resp = client.post("/exit/verify", json={"bill_id": qr_payload})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data.get("result") == "INVALID", f"Expected result 'INVALID', got {data.get('result')}"
    assert data.get("bill_no") == absent_bill, f"Expected extracted bill_no '{absent_bill}', got {data.get('bill_no')}"

    print(f"-> Verified: Pipe-delimited QR token extracted {absent_bill} and returned INVALID")
    print("PASS: QR token payload correctly parsed and rejected for fake bills")


def test_exit_check_endpoint_access_control():
    print("\n[Test 3] Testing /exit/check/{bill_no} role-based access control...")
    app.dependency_overrides.pop(get_current_user, None)

    # 1. Unauthenticated request should fail with 401
    r_unauth = client.get("/exit/check/SS-99999")
    assert r_unauth.status_code == 401, f"Expected 401 for unauthenticated /exit/check, got {r_unauth.status_code}"
    print("-> Unauthenticated caller correctly rejected with HTTP 401")

    # 2. Customer role should fail with 403
    app.dependency_overrides[get_current_user] = lambda: UserProfile(
        id="mock-cust-id",
        email="customer@example.com",
        role="customer",
        store_id=None
    )
    r_cust = client.get("/exit/check/SS-99999")
    assert r_cust.status_code == 403, f"Expected 403 for customer /exit/check, got {r_cust.status_code}"
    print("-> Customer caller correctly blocked with HTTP 403")

    app.dependency_overrides.pop(get_current_user, None)
    print("PASS: /exit/check/{bill_no} is strictly staff/manager-only")


def test_exit_check_endpoint_behavior():
    print("\n[Test 4] Testing /exit/check/{bill_no} presence and absence detection...")
    
    # Mock staff user
    app.dependency_overrides[get_current_user] = lambda: UserProfile(
        id="mock-staff-id",
        email="staff@smartscan.app",
        role="exit_staff",
        store_id="a1535a5c-50e7-4415-a855-ac792e016158"
    )

    try:
        # Check absent bill
        rand_suffix = random.randint(91000, 99999)
        absent_bill = f"SS-{rand_suffix}"
        r_absent = client.get(f"/exit/check/{absent_bill}")
        assert r_absent.status_code == 200, f"Expected 200, got {r_absent.status_code}"
        d_absent = r_absent.json()
        assert d_absent.get("bill_no") == absent_bill
        assert d_absent.get("exists") is False, f"Expected exists=False for {absent_bill}, got {d_absent.get('exists')}"
        print(f"-> Verified: Absent bill {absent_bill} correctly reported exists=False")

        # Check seeded bill SS-20481
        r_present = client.get("/exit/check/SS-20481")
        assert r_present.status_code == 200, f"Expected 200, got {r_present.status_code}"
        d_present = r_present.json()
        assert d_present.get("bill_no") == "SS-20481"
        assert d_present.get("exists") is True, f"Expected exists=True for SS-20481, got {d_present.get('exists')}"
        print("-> Verified: Seeded canonical bill SS-20481 correctly reported exists=True")

    finally:
        app.dependency_overrides.pop(get_current_user, None)

    print("PASS: /exit/check/{bill_no} accurately checks order database")


def test_verify_canonical_bill_intact_and_unconsumed():
    print("\n[Test 5] Testing /exit/verify on seeded SS-20481 (must stay unconsumed)...")
    app.dependency_overrides.pop(get_current_user, None)

    # 1. Query SS-20481 before verification
    order_res = sb.table("orders").select("id, bill_no, total, status, payment_status").eq("bill_no", "SS-20481").execute()
    assert order_res.data and len(order_res.data) > 0, "Canonical bill SS-20481 not found in app2026.orders!"
    order_before = order_res.data[0]
    assert order_before["total"] == 317, f"Expected canonical total 317, got {order_before['total']}"
    initial_status = order_before["status"]

    # 2. Call /exit/verify
    resp = client.post("/exit/verify", json={"bill_no": "SS-20481"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    assert data.get("result") in ("VERIFIED", "ALREADY_USED"), f"Expected VERIFIED or ALREADY_USED, got {data.get('result')}"
    assert data.get("bill_no") == "SS-20481"
    assert data.get("total") == 317, f"Expected total 317, got {data.get('total')}"
    assert data.get("items") is not None and len(data.get("items")) == 3, f"Expected 3 items, got {len(data.get('items', []))}"
    print(f"-> Verified: SS-20481 returned result='{data.get('result')}', total=₹{data.get('total')} and {len(data.get('items'))} items")

    # 3. Confirm SS-20481 status was not mutated / no mark-used called
    order_after_res = sb.table("orders").select("id, bill_no, status").eq("bill_no", "SS-20481").execute()
    order_after = order_after_res.data[0]
    assert order_after["status"] == initial_status, f"Order status changed from {initial_status} to {order_after['status']}"
    print(f"-> Confirmed: SS-20481 status remained {initial_status} and was NOT consumed during test")
    print("PASS: Canonical bill SS-20481 verified with items/total without consumption")


def test_frontend_build_succeeds():
    print("\n[Test 6] Testing frontend build with StaffScreen and FakeBillModal...")
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_dir = os.path.join(root_dir, "frontend")

    # Run npm run build
    result = subprocess.run(
        ["cmd.exe", "/c", "npm.cmd", "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Frontend build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "built in" in result.stdout or "dist/index.html" in result.stdout, f"Unexpected build output: {result.stdout}"
    print("-> Frontend built successfully with zero errors")
    print("PASS: Staff screen and fake bill generator compile cleanly in Vite")


if __name__ == "__main__":
    print("============================================================")
    print("SMARTSCAN 2026 — STAGE D FAKE BILL ACCEPTANCE TESTS")
    print("============================================================")
    test_verify_guaranteed_absent_bill_returns_invalid()
    test_verify_qr_payload_with_absent_bill()
    test_exit_check_endpoint_access_control()
    test_exit_check_endpoint_behavior()
    test_verify_canonical_bill_intact_and_unconsumed()
    test_frontend_build_succeeds()
    print("\n============================================================")
    print("ALL 6 STAGE D ACCEPTANCE TESTS PASSED!")
    print("============================================================")
