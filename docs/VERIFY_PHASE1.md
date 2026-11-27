# SmartScan 2026 - Phase 1 Verification Guide (step-by-step)

Do tareeke hain: **Route 1 (automated, 1 minute)** aur **Route 2 (manual, app me haath se - jury ko dikhane layak)**. Pehle setup, phir dono route.

## Setup (dono route ke liye)

1. **Backend chalao** - terminal me:
   ```
   cd D:\smartscan-2026\backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Browser me `http://localhost:8000/docs` kholo - API ki list dikhe to backend zinda hai.
2. **Frontend chalao** - dusre terminal me:
   ```
   cd D:\smartscan-2026\frontend
   npm run dev -- --host
   ```
   Laptop par `http://localhost:5173`, phone par laptop ke IP se (jaise `http://192.168.x.x:5173`, same WiFi). Tip: phone par camera scan kabhi kabhi sirf secure (HTTPS/localhost) par chalta hai - na chale to manual barcode entry use karo, wahi asal test hai.

## Demo accounts (sabka ek hi password: jo seed.py me set hai)

| Account | Role | Store |
|---|---|---|
| demo@smartscan.app | Customer | - |
| anubhav@smartscan.app | Customer | - |
| staff@smartscan.app | Exit staff | FreshMart |
| manager@smartscan.app | Manager | FreshMart |
| manager-sh@smartscan.app | Manager | StyleHub |

## Route 1 - Automated (sabse tez saboot)

```
cd D:\smartscan-2026\backend
python test_phase1.py
```
**Expected: 7/7 PASS.** Har test kya bolta hai:
- Test 0: `/stores` me exactly 3 stores (schema isolation sahi hai)
- Test 1: ₹317 cart, bill VERIFIED, reuse par ALREADY_USED, nakli bill INVALID
- Test 2: double pay par same bill, stock sirf ek baar gira
- Test 3: bottle FM ₹499 / SH ₹549
- Test 4: stock-0 product reject
- Test 5: cash flow pura
- Test 6: dusre store ke manager ko 403

## Route 2 - Manual (app me, ek ek scene)

**Scene 0 - Connection proof:** App kholo, login ke baad store list dekho. Sirf **3 stores** (FreshMart, StyleHub, DailyNeeds) dikhne chahiye. 103 dikhe = galat schema (aisa hoga nahi, test ho chuka hai).

**Scene 1 - Canonical cart + exit (sabse bada scene):**
1. `demo@smartscan.app` se login → **FreshMart** select karo
2. Teen products scan karo (ya barcode type karo): Milk `8901262010015`, Bread `8901063142217`, Shampoo `4902430752108`
3. Cart me total dekho - **exactly ₹317** aana chahiye
4. **Mock Pay** dabao → QR bill milega (SS-xxxxx)
5. Logout → `staff@smartscan.app` se login → **Staff Gate**
6. Bill ka QR scan karo / bill number dalo → **VERIFIED** aana chahiye
7. **Use** karo → wahi bill dobara verify karo → **ALREADY_USED**
8. `SS-99999` dalo → **INVALID**

**Scene 2 - Double-tap (idempotency):** Naya cart banao, Pay **do baar** dabao. Ek hi bill number milega, My Orders me ek hi order dikhega.

**Scene 3 - Ek barcode, do daam:** FreshMart me bottle `8901234567890` scan karo → **₹499**. Store badal kar StyleHub me wahi scan karo → **₹549**.

**Scene 4 - Stock khatm:** FreshMart me Coca-Cola (stock 0) cart me dal kar checkout ki koshish karo → backend **reject** karega (stock nahi hai).

**Scene 5 - Cash flow:** Customer se cash wala checkout karo → order **CASH_PENDING** banega → staff login → cash pending list me **Confirm** karo → bill active → exit par verify → **VERIFIED**.

**Scene 6 - Manager ki seema:** `manager@smartscan.app` se login → sirf FreshMart ke products dikhenge. (Dusre store par 403 API level par hai - ye automated Test 6 se proven hai.)

**Scene 7 - Unknown scan:** Koi aisa barcode scan karo jo catalogue me nahi hai (jaise `8909999888877`) → "Product not found" aayega, aur ye scan manager ke **unknown queue** me chala jayega (Phase 2 me ispar pura kaam hoga).

## Kuch fail ho to

1. Backend wale terminal ki aakhri 10-15 lines dekho - error wahi likha hota hai
2. Uska screenshot Muse ko bhejo - wahi se fix milega
3. Ghabrana nahi: database aur code dono safe hain, seed dobara chalane se demo data hamesha wapas aa jata hai (`python seed.py`)
