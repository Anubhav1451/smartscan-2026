"""
SmartScan 2026 — Core GST Master Rules and Breakup Engine
Intra-state GST (CGST + SGST only, no IGST).
Prices are GST-INCLUSIVE (MRP style). Totals never change.

Proof case:
Milk Rs 62 (0%) + Bread Rs 45 (0%) + H&S Shampoo Rs 210 (5%) = Rs 317
- 0% slab: taxable 107.00, tax 0.00
- 5% slab: taxable 200.00, tax 10.00 (CGST 5.00 + SGST 5.00)
- Grand total: 317.00
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict

VALID_GST_RATES = {0, 5, 12, 18, 28}

def default_gst_rate(category: Optional[str], name: Optional[str], price: int) -> int:
    """
    Computes default GST rate based on category, product name, and price:
    - Fresh staples (milk & bread by name, or Bakery category) = 0%
    - Electronics / Appliances = 18%
    - Clothing / Footwear / Apparel: 5% if price <= 2500 else 18%
    - Packaged grocery & FMCG & all others = 5%
    """
    clean_name = (name or "").strip().lower()
    clean_cat = (category or "").strip().lower()

    # 1. Fresh staples (milk and bread)
    if "milk" in clean_name or "bread" in clean_name:
        return 0
    if clean_cat == "bakery":
        return 0

    # 2. Electronics / Appliances
    if clean_cat in ("electronics", "appliances"):
        return 18

    # 3. Clothing / Footwear / Apparel
    if clean_cat in ("clothing", "footwear", "apparel"):
        return 5 if price <= 2500 else 18

    # 4. Default for FMCG, Groceries, Beverages, Household, etc.
    return 5

def compute_gst_breakup(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes GST slab-wise breakup back-calculated from inclusive prices.
    Breakup is calculated PER SLAB on slab totals (not per item) to eliminate rounding drift.
    
    Formula per slab:
      slab_total = sum(price * qty for items in slab)
      taxable = round(slab_total / (1 + rate / 100), 2)
      tax = round(slab_total - taxable, 2)
      cgst = round(tax / 2, 2)
      sgst = round(tax - cgst, 2)
      
    Returns a dict with:
      - 'slabs': list of {rate, taxable_value, cgst, sgst, tax, slab_total}
      - 'totals': {taxable_value, cgst, sgst, tax, grand_total}
      - 'breakup_rows': list of slabs with 'Total' summary row appended
    """
    if not items:
        return {
            "slabs": [],
            "totals": {
                "taxable_value": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "tax": 0.0,
                "grand_total": 0
            },
            "breakup_rows": [
                {
                    "rate": "Total",
                    "taxable_value": 0.0,
                    "cgst": 0.0,
                    "sgst": 0.0,
                    "tax": 0.0,
                    "slab_total": 0
                }
            ]
        }

    # Group total inclusive amount by gst_rate
    slab_totals = defaultdict(int)
    for it in items:
        rate = it.get("gst_rate")
        if rate is None:
            # Fallback to category/name rule if missing
            rate = default_gst_rate(it.get("category"), it.get("name"), it.get("price", 0))
        rate = int(rate)
        line_total = int(it.get("price", 0)) * int(it.get("qty", 1))
        slab_totals[rate] += line_total

    slabs = []
    tot_taxable = 0.0
    tot_cgst = 0.0
    tot_sgst = 0.0
    tot_tax = 0.0
    tot_grand = 0

    # Sort slabs by rate ascending (e.g. 0%, 5%, 12%, 18%, 28%)
    for rate in sorted(slab_totals.keys()):
        slab_total = slab_totals[rate]
        tot_grand += slab_total

        if rate == 0:
            taxable = float(round(slab_total, 2))
            tax = 0.0
            cgst = 0.0
            sgst = 0.0
        else:
            taxable = round(slab_total / (1.0 + rate / 100.0), 2)
            tax = round(slab_total - taxable, 2)
            cgst = round(tax / 2.0, 2)
            sgst = round(tax - cgst, 2)

        slabs.append({
            "rate": rate,
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "tax": tax,
            "slab_total": slab_total
        })

        tot_taxable = round(tot_taxable + taxable, 2)
        tot_cgst = round(tot_cgst + cgst, 2)
        tot_sgst = round(tot_sgst + sgst, 2)
        tot_tax = round(tot_tax + tax, 2)

    totals = {
        "taxable_value": tot_taxable,
        "cgst": tot_cgst,
        "sgst": tot_sgst,
        "tax": tot_tax,
        "grand_total": tot_grand
    }

    breakup_rows = list(slabs)
    breakup_rows.append({
        "rate": "Total",
        "taxable_value": tot_taxable,
        "cgst": tot_cgst,
        "sgst": tot_sgst,
        "tax": tot_tax,
        "slab_total": tot_grand
    })

    return {
        "slabs": slabs,
        "totals": totals,
        "breakup_rows": breakup_rows
    }
