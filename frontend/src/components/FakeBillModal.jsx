import React, { useState, useEffect } from 'react';
import { 
  X, 
  Printer, 
  RefreshCw, 
  Copy, 
  Check, 
  ShieldAlert, 
  ArrowRight,
  Loader2,
  FileText
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../services/api';

const SAMPLE_ITEMS = [
  { name: 'Amul Taaza Toned Milk 500ml', barcode: '8901262010015', qty: 2, price: 27, gst_rate: 0 },
  { name: 'Britannia 100% Whole Wheat Bread 400g', barcode: '8901063142217', qty: 1, price: 50, gst_rate: 0 },
  { name: "Lay's Magic Masala Potato Chips 50g", barcode: '8901491101836', qty: 2, price: 20, gst_rate: 12 },
];

export default function FakeBillModal({ isOpen, onClose, onTestVerify, storeName = 'FreshMart (Demo)' }) {
  const [billNo, setBillNo] = useState('');
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatedDate, setGeneratedDate] = useState('');

  // Calculate totals
  const subtotal = SAMPLE_ITEMS.reduce((sum, it) => sum + (it.price * it.qty), 0);
  const gstAmount = 4.28; // Estimated GST on taxable items
  const grandTotal = subtotal; // ₹144

  const generateFakeBillNumber = async () => {
    setGenerating(true);
    setCopied(false);
    try {
      let candidate = '';
      let isAbsent = false;

      // Try up to 5 times to ensure guaranteed-absent bill in app2026.orders
      for (let attempt = 0; attempt < 5; attempt++) {
        const rand = Math.floor(90000 + Math.random() * 9999);
        candidate = `SS-${rand}`;
        try {
          const check = await api.checkBillExists(candidate);
          if (!check.exists) {
            isAbsent = true;
            break;
          }
        } catch (e) {
          try {
            const vRes = await api.verifyExitBill(candidate);
            if (vRes.result === 'INVALID') {
              isAbsent = true;
              break;
            }
          } catch (e2) {
            isAbsent = true;
            break;
          }
        }
      }

      setBillNo(candidate);
      const now = new Date();
      setGeneratedDate(now.toLocaleString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      }));
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      generateFakeBillNumber();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const qrPayload = `SMARTSCAN|BILL|${billNo}|fake-${Date.now()}|FM|${grandTotal}`;

  const handleCopy = () => {
    if (!billNo) return;
    navigator.clipboard.writeText(billNo);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  const handleTestNow = () => {
    if (onTestVerify && billNo) {
      onTestVerify(billNo);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <style>{`
        @media print {
          body * {
            visibility: hidden !important;
          }
          #printable-fake-receipt, #printable-fake-receipt * {
            visibility: visible !important;
          }
          #printable-fake-receipt {
            position: absolute !important;
            left: 50% !important;
            top: 20px !important;
            transform: translateX(-50%) !important;
            width: 380px !important;
            max-width: 100% !important;
            background: white !important;
            color: black !important;
            border: 2px dashed #999 !important;
            padding: 16px !important;
            box-shadow: none !important;
          }
          .no-print {
            display: none !important;
          }
        }
      `}</style>

      <div className="bg-white rounded-card w-full max-w-md max-h-[92vh] flex flex-col shadow-2xl border border-surface-tint overflow-hidden">
        {/* Modal Top Header (no-print) */}
        <div className="px-5 py-3 border-b border-surface-tint flex items-center justify-between bg-cream/70 no-print">
          <div className="flex items-center gap-2">
            <span className="p-1 rounded bg-amber-100 text-amber-800">
              <FileText className="w-4 h-4" />
            </span>
            <div>
              <h3 className="font-bold text-xs text-ink">Sample FAKE Bill Generator</h3>
              <p className="text-[10px] text-ink-muted">Jury & exit fraud testing tool</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-neutral-200 text-ink-muted transition"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Action Toolbar (no-print) */}
        <div className="px-5 py-2.5 bg-neutral-50 border-b border-surface-tint flex flex-wrap items-center justify-between gap-2 no-print">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={generating}
              onClick={generateFakeBillNumber}
              className="px-2.5 py-1.5 bg-white hover:bg-surface-tint text-ink text-xs font-semibold rounded border border-surface-tint flex items-center gap-1 shadow-2xs transition disabled:opacity-60"
              title="Pick a new fake bill number"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
              <span>Regenerate</span>
            </button>
            <button
              type="button"
              onClick={handleCopy}
              className="px-2.5 py-1.5 bg-white hover:bg-surface-tint text-ink text-xs font-semibold rounded border border-surface-tint flex items-center gap-1 shadow-2xs transition"
              title="Copy bill number"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy No'}</span>
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handlePrint}
              className="px-3 py-1.5 bg-primary hover:bg-primary-dark text-white text-xs font-bold rounded flex items-center gap-1 shadow-xs transition"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print Bill</span>
            </button>
          </div>
        </div>

        {/* Scrollable Receipt Container */}
        <div className="flex-1 overflow-y-auto p-5 bg-neutral-100 flex justify-center">
          {generating ? (
            <div className="py-20 flex flex-col items-center justify-center text-ink-muted gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
              <span className="text-xs font-medium">Generating unique absent bill...</span>
            </div>
          ) : (
            <div
              id="printable-fake-receipt"
              className="relative w-full max-w-[340px] bg-white rounded-card-sm p-4 border border-surface-tint shadow-md font-mono text-xs text-ink space-y-3 overflow-hidden select-text"
            >
              {/* WATERMARK OVERLAY (SCREEN & PRINT) */}
              <div 
                aria-hidden="true"
                className="absolute inset-0 flex items-center justify-center pointer-events-none select-none z-20 overflow-hidden"
              >
                <div className="rotate-[-32deg] border-4 border-dashed border-red-600/40 text-red-600/35 font-black text-2xl tracking-widest uppercase px-4 py-2 rounded-lg text-center whitespace-nowrap bg-white/10 backdrop-blur-[0.5px]">
                  SAMPLE - NOT A REAL BILL
                </div>
              </div>

              {/* Receipt Header */}
              <div className="text-center border-b border-dashed border-neutral-300 pb-2 space-y-0.5">
                <h4 className="font-bold text-sm tracking-tight text-ink uppercase">
                  {storeName}
                </h4>
                <p className="text-[10px] text-ink-muted font-sans">
                  Store #101 · Rajpur Road, Dehradun
                </p>
                <p className="text-[9px] text-ink-muted font-sans">
                  GSTIN: 05AAACF1234M1Z5 · Tel: 0135-2654321
                </p>
                <div className="pt-1">
                  <span className="inline-block bg-neutral-100 text-[9px] font-sans font-bold text-ink-muted px-2 py-0.5 rounded uppercase">
                    Tax Invoice / Cash Memo
                  </span>
                </div>
              </div>

              {/* Bill Reference & Date */}
              <div className="text-[11px] space-y-0.5 border-b border-dashed border-neutral-300 pb-2">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Bill No:</span>
                  <span className="font-extrabold text-ink">{billNo}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Date:</span>
                  <span>{generatedDate || '28 Nov 2026, 11:30 AM'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">POS:</span>
                  <span>Gate-01 (Self-Checkout)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Payment:</span>
                  <span className="font-bold text-emerald-700">UPI / PAID (MOCK)</span>
                </div>
              </div>

              {/* Items List */}
              <div className="space-y-1.5 border-b border-dashed border-neutral-300 pb-2">
                <div className="flex justify-between text-[10px] font-bold text-ink-muted uppercase border-b border-neutral-200 pb-0.5">
                  <span>Item</span>
                  <span>Qty × Rate = Amt</span>
                </div>
                {SAMPLE_ITEMS.map((item, idx) => (
                  <div key={idx} className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="font-medium truncate max-w-[170px]">{item.name}</span>
                      <span className="font-semibold text-right">₹{item.price * item.qty}</span>
                    </div>
                    <div className="flex justify-between text-[9px] text-ink-muted font-sans">
                      <span>Barcode: {item.barcode}</span>
                      <span>{item.qty} × ₹{item.price} (GST {item.gst_rate}%)</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Totals */}
              <div className="text-[11px] space-y-1 border-b border-dashed border-neutral-300 pb-2">
                <div className="flex justify-between text-ink-muted">
                  <span>Subtotal:</span>
                  <span>₹{subtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-ink-muted">
                  <span>CGST (6% on Snacks):</span>
                  <span>₹{(gstAmount / 2).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-ink-muted">
                  <span>SGST (6% on Snacks):</span>
                  <span>₹{(gstAmount / 2).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm font-extrabold pt-1 border-t border-neutral-200">
                  <span>TOTAL AMOUNT:</span>
                  <span className="text-primary font-black">₹{grandTotal.toFixed(2)}</span>
                </div>
              </div>

              {/* QR Code Section */}
              <div className="flex flex-col items-center justify-center pt-1 space-y-1.5">
                <div className="p-2 bg-white rounded border border-neutral-200 shadow-2xs">
                  <QRCodeSVG
                    value={qrPayload}
                    size={130}
                    level="H"
                    includeMargin={true}
                  />
                </div>
                <p className="text-[9px] text-ink-muted font-sans text-center">
                  Scan QR at Exit Gate or enter <strong className="font-mono text-ink">{billNo}</strong>
                </p>
              </div>

              {/* Footer */}
              <div className="text-center pt-2 text-[9px] text-ink-muted font-sans border-t border-dashed border-neutral-300 space-y-0.5">
                <p className="font-semibold text-alert">*** JURY TEST RECEIPT ***</p>
                <p>Not recorded in system • Verification will reject</p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Bottom Action Bar (no-print) */}
        <div className="p-4 bg-cream/70 border-t border-surface-tint flex gap-2 no-print">
          <button
            type="button"
            disabled={!billNo || generating}
            onClick={handleTestNow}
            className="flex-1 py-2.5 bg-alert hover:bg-alert/90 text-white font-bold text-xs rounded-card-sm transition flex items-center justify-center gap-1.5 shadow-sm"
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Test Verify in Gate Scanner</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 bg-neutral-200 hover:bg-neutral-300 text-ink font-semibold text-xs rounded-card-sm transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
