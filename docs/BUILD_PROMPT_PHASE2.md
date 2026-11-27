# BUILD PROMPT - Phase 2 (paste into Antigravity)

Continue building **SmartScan 2026** in this repository. Phase 1 is complete and verified (7/7 acceptance tests passing - see `docs/BUILD_PROMPT_PHASE1.md` and `docs/VERIFY_PHASE1.md`). Follow `docs/BUILD_PLAN.md`; Phase 1 rules still apply in full: same Supabase project, schema **`app2026`** on every table-touching client (backend AND seed), never touch the `public` schema or the old project, server-side money logic only, frontend Supabase client for auth only, clean error messages, small commits on `main`, push when done.

## SELF-TEST RULE (mandatory - learned from a Phase 1 bug)

API tests passing does NOT mean the app works. In Phase 1 every API test passed while the app showed every product as out of stock (the frontend checked a field the API never sends). Before you report Phase 2 complete, you MUST:
1. Run the backend AND the frontend dev server.
2. Click through every screen and flow yourself, as each role: customer login → store select → scan (manual entry is fine) → add to cart → checkout → pay → bill; staff login → exit verify + cash confirm; manager login → every new Phase 2 screen (scan-to-add, CSV import, unknown queue, dashboard, sticker print).
3. Fix every bug you find and re-test that flow until it is clean.
4. Only then run the acceptance tests below and report - with a line confirming the app was run and clicked through, not just the API tests.

## Build these (Phase 2 - retailer onboarding + dashboard + hardening)

1. **Scan-to-add (manager):** manager scans a barcode (camera or manual entry), fills name, brand, category, price, MRP, stock, unit, and saves - the product is live instantly. `POST /manager/stores/{store_id}/products`. Duplicate `(store_id, barcode)` returns **409** with a clean message. Remember: a barcode is just an ID; all details live in our DB against `store_id + barcode`.
2. **Product search + quick edit:** manager product list gets search (name or barcode) and inline edit of price and stock.
3. **CSV bulk import:** downloadable template with columns `barcode,name,brand,category,price,mrp,stock,unit`.
   - `POST /manager/stores/{store_id}/products/import-preview` - dry run only, saves nothing. Returns total rows, Add count, Update count, Fail count, and per-row errors with reasons.
   - `POST /manager/stores/{store_id}/products/import` - applies the file as an upsert on `(store_id, barcode)`.
   - Validation: barcode and name required; price and stock must be whole numbers >= 0 (decimals like 145.50 are rejected); blank rows skipped.
4. **Unknown-scan queue (manager screen):** list this store's rows from `app2026.unknown_scans` (barcode, count, last seen, newest first). Actions: **Add product** (form prefilled with the barcode; on save the queue row is removed) and **Dismiss** (removes the row).
5. **Barcode sticker print:** for any product, a print-friendly sticker view showing an EAN-13 barcode graphic (use JsBarcode), product name and price.
6. **Manager dashboard (replace the placeholder):** today's orders count + revenue, last-7-days sales chart, top 5 products by quantity, recent orders list, low-stock list (stock <= 5), and an SDG impact panel: estimated queue time saved = paid orders x 4 minutes, paper bills avoided = paid orders. Label the panel clearly as estimates.
7. **Demo reset:** `POST /manager/demo-reset` re-runs the seed for schema `app2026` only. Seed products are upserted; **manager-added (custom) products must survive the reset**; orders return to the 40 seed orders.
8. **Hardening:**
   - Rate limiting: sliding-window limiter - generous global limit per IP, stricter on `/scan` and `/checkout`; over the limit returns **429** with a clean message.
   - Re-verify the atomic stock decrement still holds under two simultaneous checkouts of the last unit.
   - Error-hygiene sweep: no endpoint leaks stack traces, SQL, or file paths.
   - `GET /health` returns `{"status": "ok"}`.

## Acceptance tests (new file `backend/test_phase2.py`, run all, report numbers)

1. Scan-to-add: manager adds barcode `8907777666655` "Test Biscuits" ₹40, stock 10 at FreshMart → a customer scan returns it at ₹40.
2. Adding the same barcode again at FreshMart returns 409.
3. CSV preview with a 6-row file (3 new, 1 existing-barcode update, 2 invalid) returns Add 3 / Update 1 / Fail 2 with reasons, and saves nothing; after confirm-import, the catalogue reflects the 3 adds + 1 update and the invalid rows are absent.
4. Unknown queue: customer scans `8909999888877` twice → queue shows it with count 2 → manager adds the product from the queue → queue row gone → customer scan now succeeds.
5. Dashboard: today's orders/revenue match the database; the low-stock list includes the stock-0 Coca-Cola at FreshMart.
6. Rate limit: firing requests rapidly at `/scan` produces a 429.
7. Demo reset: a custom product added in test 1 is still present after reset; orders are back to 40; the canonical ₹317 cart works again.
8. Regression: `backend/test_phase1.py` still passes 7/7.

Report: files changed, test results with numbers, anything skipped and why.
