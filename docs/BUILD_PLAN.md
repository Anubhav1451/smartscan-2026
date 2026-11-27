# SmartScan 2026 - Build Plan

Built at HIMOVATION 2026 (AI for Smart City, SDG 11 + SDG 12) - Team IDEONIX.
Evaluations: **Phase 1 - 27 Nov 3:00 PM · Phase 2 - 27 Nov 9:00 PM · Phase 3 - 28 Nov 9:00 AM.**

## The product in one line

Multi-retailer Scan-and-Go: the customer selects the store in-app (no store QR), scans barcodes, pays in-app, and exits with a QR-verified digital bill. The retailer runs their own catalogue and staff from a dashboard.

## Roles

- **Customer** - store select, scan, cart, pay, QR bill, order history
- **Manager (per store)** - products (scan-to-add, CSV import, quick edit), unknown-scan queue, dashboard, demo reset
- **Exit staff (per store)** - bill verification (VERIFIED / ALREADY_USED / INVALID), cash confirmation, RFID-style bag check (simulated, labelled as such)

## Phase 1 - core flow (by 3:00 PM)

- Project scaffold: `frontend/` (Vite React + Tailwind PWA) + `backend/` (FastAPI)
- Auth via Supabase; backend verifies JWT (JWKS), role + store resolved server-side via `/auth/me`
- Screens: login, store list, store page (scan-first), cart, bill, my orders; staff gate; manager shell
- APIs: `GET /stores`, `GET /stores/{id}/products`, `POST /scan`, `POST /checkout`, `POST /orders/{id}/pay/mock`, `POST /orders/{id}/pay/cash`, `POST /exit/verify`, `POST /exit/use`, `GET /orders/my`
- Non-negotiables:
  - Totals computed **server-side only**; the frontend's numbers are never trusted for money
  - **Idempotent checkout**: checkout creates ONE pending order; pay flips it to paid and issues its bill - double-tap or retry returns the same bill, stock drops exactly once
  - **Single-use bills**: verify marks a bill used; reuse shows ALREADY_USED; unknown bill shows INVALID
  - Products are store-scoped: identity is `(store_id, barcode)` - the same barcode can have a different price/stock per store
- Seed: 3 demo stores + 16 products + 40 orders + demo accounts (below). Canonical demo cart must total exactly **₹317** (Milk ₹62 + Whole Wheat Bread ₹45 + Head & Shoulders Shampoo 340ml ₹210), canonical bill **SS-20481**

## Phase 2 - retailer onboarding + dashboard (by 9:00 PM)

- **Scan-to-add**: manager scans a real barcode, fills name/price/stock - product goes live instantly (a barcode is just an ID; all details live in our DB against `store_id + barcode`)
- **CSV bulk import**: dry-run preview (Add / Update / Fail counts with reasons) then confirm; upsert on `(store_id, barcode)`; price and stock are whole numbers
- **Unknown-scan queue**: a customer scan that misses the catalogue is logged to the store's queue **in the database** (survives restarts); manager adds the product from the queue in one tap
- **Barcode sticker print** for products that have no printed barcode
- **Manager dashboard**: today's KPIs, 7-day sales chart, top products, recent orders, low-stock alerts, SDG impact panel (queue time saved = paid orders x 4 min, paper bills avoided - labelled as estimates)
- **Hardening**: rate limiting (429), atomic stock decrement (no oversell on the last unit), clean error messages (no stack traces or internal details leaked)
- **Demo reset** restores seed data but never deletes manager-added products

## Phase 3 - network layer + polish (by 28 Nov 9:00 AM)

- **Dehradun Network (simulated)**: 100 fictional stores (codes NW01-NW100) across 13 Dehradun localities, ~3,300 products, ~9,900 orders over 7 days (bills SS-70001+) - every network store is fully checkout-able, not just a list entry. Stage line: "simulated live network" - never claim the stores are really onboarded
- Store list: **search + area chips**, demo stores pinned first, count line ("103 stores - 14 areas - Dehradun")
- Final rehearsal, Q&A prep, backup screenshots/video of the full demo flow

## Data model (PostgreSQL on Supabase, schema `app2026`)

`retailers, stores, products, profiles, orders, order_items, exit_verifications, unknown_scans` - all inside the new schema `app2026` (SQL in `docs/SCHEMA_SQL.md`).
RLS on; service-role key stays server-side only, never in the frontend or in code.

## Demo data

- Stores: **FreshMart** (FM, Rajpur Road) - **StyleHub** (SH, Rajpur Road) - **DailyNeeds** (DN, Subhash Nagar)
- Known products: Amul Taaza Milk 500ml `8901262010015` ₹62 · Britannia Whole Wheat Bread `8901063142217` ₹45 · Head & Shoulders Shampoo 340ml `4902430752108` ₹210 · Steel Water Bottle 1L `8901234567890` ₹499 at FM / ₹549 at SH · Tata Salt 1kg `8904043901005` ₹28 · Coca-Cola 750ml stock 0 at FM (out-of-stock scene)
- Accounts (one shared demo password, set in seed): `demo@smartscan.app` (customer), `anubhav@smartscan.app` (customer), `staff@smartscan.app` (exit staff, FM), `manager@smartscan.app` (manager, FM), `manager-sh@smartscan.app` (manager, SH)

## Infrastructure

- **Supabase**: existing project, but a fresh schema `app2026` for this build - new tables, new seed; the old app's `public` data stays untouched (decided at the venue, 27 Nov). Demo auth accounts already exist in the project and are reused. Connection values live only in `.env` files, never in code or in this repo.
- **Backend**: new Render service from this repo (Phase 1 may run locally first).
- **Frontend**: new Vercel project from this repo.

## Design

SmartScan Green - deep green `#14532D`, dark green `#0C3B21`, cream `#F6F2E7`, ink `#16130E`, success `#16A34A`. Red only for alerts. Logo: shopping bag with a check mark. Tagline: **Scan. Pay. Walk Out.**
