# SmartScan 2026

**Scan. Pay. Walk Out.**

SmartScan is a multi-retailer Scan-and-Go checkout app, **built at HIMOVATION 2026** (Solve-a-Thon: AI for SDGs, SRHU Jolly Grant, Dehradun) by **Team IDEONIX** under the theme **AI for Smart City**.

Shoppers select a store in the app, scan product barcodes with their phone camera, pay in-app, and walk out with a QR-verified digital bill - no billing queue. Retailers onboard themselves: scan-to-add products, CSV bulk import, and an unknown-scan queue that turns missed scans into catalogue entries.

## Build plan (24 hours, 3 evaluation phases)

- **Phase 1 (27 Nov, 3:00 PM):** core flow end to end - auth + roles, store selection, barcode scan, cart, idempotent checkout, mock payment, QR bill, exit verification.
- **Phase 2 (27 Nov, 9:00 PM):** retailer onboarding - scan-to-add, CSV import with dry-run preview, unknown-scan queue, manager dashboard, hardening.
- **Phase 3 (28 Nov, 9:00 AM):** Dehradun network layer (100 simulated stores, 13 localities), store search + area filters, demo reset, final polish.

Full plan: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) · Phase 1 prompt: [docs/BUILD_PROMPT_PHASE1.md](docs/BUILD_PROMPT_PHASE1.md)

## Stack

- **Frontend:** React (Vite) + Tailwind CSS, PWA, ZXing barcode scanning
- **Backend:** Python FastAPI (Uvicorn) - all money logic (prices, totals, stock) lives server-side
- **Database + Auth:** Supabase (PostgreSQL), JWT verified on the backend via JWKS; role and store resolved server-side
- **Design:** SmartScan Green - deep green `#14532D` / `#0C3B21`, cream `#F6F2E7`, bag-with-check logo

## Status

Built at HIMOVATION 2026, 27-28 Nov 2026. All work in this repository is done during the event.
