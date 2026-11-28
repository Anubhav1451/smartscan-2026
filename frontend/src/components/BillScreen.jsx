import React, { useState, useEffect } from 'react';
import { 
  ChevronLeft, 
  CheckCircle2, 
  QrCode, 
  ShoppingBag, 
  Home, 
  Clock, 
  ShieldCheck, 
  FileText,
  Share2
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../services/api';

export default function BillScreen({ onNavigate, billData }) {
  const [bill, setBill] = useState(billData?.bill || billData || null);

  const billNo = bill?.bill_no || 'SS-20481';
  const qrPayload = bill?.qr_token || `SMARTSCAN|BILL|${billNo}|${bill?.id || ''}|FM|${bill?.total || 0}`;
  const total = bill?.total ?? 317;
  const storeName = bill?.stores?.name || bill?.store_name || 'SmartScan Store';
  const items = bill?.items || [];
  const status = bill?.status || 'BILL_ACTIVE';

  // Poll bill status so that when exit staff marks it USED, the bill screen reflects it!
  useEffect(() => {
    if (!billNo) return;
    const interval = setInterval(async () => {
      try {
        const fresh = await api.getBill(billNo);
        if (fresh && fresh.status !== status) {
          setBill(fresh);
        }
      } catch (e) {
        // Silent catch for background poll
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [billNo, status]);

  const isVerifiedUsed = status === 'VERIFIED_USED';
  const isMismatch = status === 'MISMATCH';

  return (
    <div className="flex flex-col h-full bg-cream text-ink select-none relative">
      {/* Top Header */}
      <header className="px-5 pt-3 pb-3 flex items-center justify-between border-b border-surface-tint bg-cream/90 backdrop-blur-xs sticky top-0 z-20">
        <button 
          type="button"
          onClick={() => onNavigate('home')}
          className="flex items-center space-x-1.5 text-xs font-semibold text-ink hover:text-primary transition-colors"
        >
          <ChevronLeft className="w-5 h-5 -ml-1" />
          <span>Home</span>
        </button>

        <span className="font-bold text-xs text-ink">Digital Receipt</span>

        <button
          type="button"
          onClick={() => onNavigate('orders')}
          className="text-xs text-primary font-semibold hover:underline"
        >
          My Orders
        </button>
      </header>

      {/* Main Body */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 pb-24">
        
        {/* Success / Status Pill Header */}
        <div className="text-center space-y-1">
          {isVerifiedUsed ? (
            <div className="inline-flex items-center gap-1.5 bg-neutral-200 text-neutral-800 px-3 py-1 rounded-full text-xs font-bold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>VERIFIED AT EXIT · USED</span>
            </div>
          ) : isMismatch ? (
            <div className="inline-flex items-center gap-1.5 bg-pending-bg text-pending px-3 py-1 rounded-full text-xs font-bold">
              <Clock className="w-3.5 h-3.5" />
              <span>UNDER REVIEW AT EXIT</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 bg-success/15 text-success px-3.5 py-1 rounded-full text-xs font-bold">
              <CheckCircle2 className="w-4 h-4 text-success" />
              <span>ACTIVE · READY FOR EXIT</span>
            </div>
          )}

          <h2 className="text-xl font-extrabold text-ink tracking-tight mt-1">
            Payment Successful
          </h2>
          <p className="text-xs text-ink-muted">
            {storeName} · {billNo}
          </p>
        </div>

        {/* QR Code Presentation Card (Prominent "Show at Exit") */}
        <div className="bg-white rounded-card p-5 border border-surface-tint shadow-md flex flex-col items-center text-center space-y-3 relative overflow-hidden">
          <div className="bg-primary text-white text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full">
            Show this QR at Exit
          </div>

          {/* QR Code */}
          <div className="p-3 bg-white rounded-card-sm border border-neutral-100 shadow-xs flex items-center justify-center">
            <QRCodeSVG
              value={qrPayload}
              size={180}
              level="H"
              includeMargin={true}
              className="rounded-xs"
            />
          </div>

          {/* Bill ID Display */}
          <div className="space-y-0.5">
            <span className="text-[11px] text-ink-muted uppercase tracking-wider font-semibold">
              Bill Reference
            </span>
            <div className="font-mono font-extrabold text-lg text-ink tracking-widest">
              {billNo}
            </div>
          </div>
        </div>

        {/* Itemized Receipt Details */}
        <div className="bg-white rounded-card p-4 border border-surface-tint shadow-xs space-y-3">
          <div className="flex justify-between items-center pb-2 border-b border-surface-tint">
            <div>
              <h4 className="font-bold text-xs text-ink">Tax Invoice Items</h4>
              <p className="text-[10px] text-ink-muted">
                {bill?.customer_mobile ? `Customer Mobile: +91 ${bill.customer_mobile}` : 'Customer Mobile: Not provided'}
              </p>
            </div>
            <span className="text-xs text-ink-muted">
              {bill?.item_count || items.reduce((s, it) => s + (it.qty || 1), 0)} item(s)
            </span>
          </div>

          <div className="space-y-2 text-xs">
            {items.map((item, idx) => {
              const name = item.name_snapshot || item.name;
              const price = item.price_snapshot || item.price;
              const qty = item.qty || 1;
              const gstRate = item.gst_rate !== undefined ? item.gst_rate : 5;
              return (
                <div key={idx} className="flex justify-between items-center">
                  <div className="truncate max-w-[200px]">
                    <span className="font-semibold text-ink">{name}</span>
                    <span className="text-ink-muted text-[11px] ml-1.5">× {qty}</span>
                    <span className="ml-1.5 text-[10px] bg-emerald-50 text-emerald-800 border border-emerald-200/60 font-semibold px-1.5 py-0.2 rounded">
                      GST {gstRate}%
                    </span>
                  </div>
                  <span className="font-bold text-ink">₹{price * qty}</span>
                </div>
              );
            })}
          </div>

          {/* Pricing & Discount Breakdown */}
          <div className="pt-2 border-t border-surface-tint space-y-1 text-xs">
            {bill?.mrp_total && bill.mrp_total > total && (
              <div className="flex justify-between text-ink-muted">
                <span>Total MRP</span>
                <span className="line-through">₹{bill.mrp_total}</span>
              </div>
            )}
            {bill?.discount && bill.discount > 0 && (
              <div className="flex justify-between text-emerald-700 font-semibold">
                <span>Total Savings / Discount</span>
                <span>-₹{bill.discount}</span>
              </div>
            )}
            <div className="pt-1.5 border-t border-surface-tint flex justify-between items-center">
              <span className="font-bold text-sm text-ink">Grand Total (Incl. GST)</span>
              <span className="font-extrabold text-base text-primary">₹{total}</span>
            </div>
          </div>
        </div>

        {/* Slab-wise GST Breakup Table */}
        {bill?.gst_breakup && bill.gst_breakup.length > 0 && (
          <div className="bg-white rounded-card p-4 border border-surface-tint shadow-xs space-y-2.5">
            <div className="flex justify-between items-center pb-1.5 border-b border-surface-tint">
              <h4 className="font-bold text-xs text-ink">GST Tax Breakup (Intra-state)</h4>
              <span className="text-[10px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full">
                CGST + SGST
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr className="border-b border-surface-tint text-ink-muted font-bold text-[10px] uppercase">
                    <th className="py-1.5 px-1">Rate</th>
                    <th className="py-1.5 px-1 text-right">Taxable (₹)</th>
                    <th className="py-1.5 px-1 text-right">CGST (₹)</th>
                    <th className="py-1.5 px-1 text-right">SGST (₹)</th>
                    <th className="py-1.5 px-1 text-right">Total Tax (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-tint/50">
                  {bill.gst_breakup.map((row, idx) => {
                    const isTotal = row.rate === 'Total';
                    return (
                      <tr key={idx} className={isTotal ? 'font-bold bg-cream/60' : 'text-ink'}>
                        <td className="py-1.5 px-1">
                          {isTotal ? 'Total' : `${row.rate}%`}
                        </td>
                        <td className="py-1.5 px-1 text-right">
                          {Number(row.taxable_value).toFixed(2)}
                        </td>
                        <td className="py-1.5 px-1 text-right">
                          {Number(row.cgst).toFixed(2)}
                        </td>
                        <td className="py-1.5 px-1 text-right">
                          {Number(row.sgst).toFixed(2)}
                        </td>
                        <td className="py-1.5 px-1 text-right text-emerald-800">
                          {Number(row.tax).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-[9px] text-ink-muted leading-relaxed">
              *Taxes are computed on slab totals back-calculated from inclusive MRP prices. Intra-state supply.
            </p>
          </div>
        )}

      </div>

      {/* Bottom Sticky Action */}
      <div className="p-4 bg-white border-t border-surface-tint flex gap-2">
        <button
          type="button"
          onClick={() => onNavigate('home')}
          className="flex-1 py-3 bg-primary hover:bg-primary-dark text-white text-xs font-semibold rounded-card transition flex items-center justify-center gap-1.5"
        >
          <Home className="w-4 h-4" />
          <span>Done (Back to Home)</span>
        </button>
      </div>
    </div>
  );
}
