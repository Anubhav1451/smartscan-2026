# BUILD PROMPT - Phase 1 (paste into Antigravity)

Build **SmartScan 2026**, a multi-retailer Scan-and-Go checkout web app, in this repository. Built at HIMOVATION 2026. Follow `docs/BUILD_PLAN.md` - where this prompt and the plan differ, the plan wins.

## Layout

- `frontend/` - Vite + React + Tailwind CSS, delivered as a PWA (installable, theme color `#14532D`)
- `backend/` - Python FastAPI (Uvicorn), thin API layer

## Design

SmartScan Green: deep green `#14532D`, dark green `#0C3B21`, cream `#F6F2E7`, ink `#16130E`, success `#16A34A`. Red only for alerts. Logo: shopping bag with a check mark inside. Tagline: "Scan. Pay. Walk Out."

## Database + auth (Supabase, already provisioned)

Tables: `retailers, stores, products, profiles, orders, order_items, exit_verifications, unknown_scans`.
Supabase Auth issues JWTs; the backend verifies them via JWKS (ES256, legacy HS256 fallback) and resolves role + store server-side via `GET /auth/me` - never trust role/store sent by the client. All secrets come from `.env` (backend: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY; frontend: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL). No secret in code, ever.

## APIs to build

- `GET /stores` - list stores
- `GET /stores/{store_id}/products` - that store's catalogue
- `POST /scan` {store_id, barcode} - product lookup within the store; on a miss, log the barcode to that store's unknown-scan queue and return 404
- `POST /checkout` {store_id, items[{barcode, qty}]} - creates ONE PENDING order, totals computed server-side from DB prices
- `POST /orders/{id}/pay/mock` - flips the order to PAID and issues its bill (bill_no `SS-xxxxx`, QR token). Idempotent: paying twice returns the same bill; stock decrements exactly once
- `POST /orders/{id}/pay/cash` + staff confirm endpoint - cash goes CASH_PENDING until staff confirms, then the bill activates
- `POST /exit/verify` {bill_no} - VERIFIED (genuine paid bill) / ALREADY_USED / INVALID
- `POST /exit/use` - marks a verified bill used
- `GET /orders/my` - the customer's orders

## Screens

Customer: login - store list (select store in-app, NO store-QR scan) - store page, scan-first (ZXing camera scanning + manual barcode entry + torch toggle) - cart - pay - QR bill - my orders.
Exit staff: staff gate only (verify bill QR, cash pending list).
Manager: store shell with products list and dashboard placeholder (full dashboard is Phase 2).

## Rules that must hold

1. A product's identity is `(store_id, barcode)` - the same barcode may exist in many stores at different prices/stock.
2. Stock decrement is conditional (only when stock >= qty) - the last unit can never be oversold.
3. Error responses are clean messages only - no stack traces, no internal details.
4. CORS allows only our own frontend origins.

## Seed (backend/seed.py, rerunnable)

- 3 stores: FreshMart (code FM, Rajpur Road, Dehradun), StyleHub (SH, Rajpur Road), DailyNeeds (DN, Subhash Nagar) - 16 products total (FM 8 / SH 4 / DN 4), 40 past orders
- Must include: Amul Taaza Milk 500ml `8901262010015` ₹62 (FM) - Britannia Whole Wheat Bread `8901063142217` ₹45 (FM) - Head & Shoulders Shampoo 340ml `4902430752108` ₹210 (FM) - Steel Water Bottle 1L `8901234567890` ₹499 at FM and ₹549 at SH - Tata Salt 1kg `8904043901005` ₹28 (FM) - one product with stock 0 at FM
- Accounts (one shared demo password, defined once in seed): demo@smartscan.app and anubhav@smartscan.app (customers), staff@smartscan.app (exit staff, FM), manager@smartscan.app (manager, FM), manager-sh@smartscan.app (manager, SH)

## Acceptance tests (run all, report numbers)

1. Canonical cart at FreshMart (milk + bread + shampoo) totals exactly ₹317; mock pay issues a bill; exit verify = VERIFIED; verify again after use = ALREADY_USED; fake bill SS-99999 = INVALID
2. Double checkout/pay of the same cart creates one order, one bill, stock drops once
3. Bottle scan shows ₹499 at FreshMart and ₹549 at StyleHub
4. Stock-0 product cannot be checked out
5. Cash flow: checkout with cash - staff confirms - bill activates - exit verify passes
6. A manager of one store calling another store's manager APIs gets 403

Work in small commits on `main`, one per working piece. Report: files created, test results with numbers, anything skipped and why.
