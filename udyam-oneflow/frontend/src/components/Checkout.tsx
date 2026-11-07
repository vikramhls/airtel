// Simulated checkout: e-sign the agreement (OTP), set up AutoPay, then place the order.
import { useEffect, useState } from "react";
import { api, type Quote } from "../api/client";
import { inr } from "../hooks/useSession";
import { useI18n } from "../i18n";
import { Button, ErrorBox, Pill } from "./ui";

type Esign = { signed: boolean; signed_on: string; document_hash: string; method: string };
type Mandate = { mandate_id: string; method: string; handle_masked: string | null; max_amount: number };

export function Checkout({ sessionId, quoteId, onDone, onClose, placing }: {
  sessionId: string; quoteId: string; onDone: () => void; onClose: () => void; placing: boolean;
}) {
  const { t } = useI18n();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [esign, setEsign] = useState<Esign | null>(null);
  const [method, setMethod] = useState<"upi_autopay" | "nach">("upi_autopay");
  const [handle, setHandle] = useState("");
  const [mandate, setMandate] = useState<Mandate | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Quote>(`/quote/${quoteId}`).then(setQuote).catch(setError);
    api.get<{ esign: Esign | null; mandate: Mandate | null }>(`/checkout/${quoteId}`).then((s) => {
      if (s.esign) { setEsign(s.esign); setStep(s.mandate ? 3 : 2); }
      if (s.mandate) setMandate(s.mandate);
    }).catch(() => undefined);
  }, [quoteId]);

  async function run(fn: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end bg-black/70" role="dialog" aria-modal="true" aria-label="Checkout">
      <div className="mx-auto max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-3xl border border-line bg-surface p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">{t.coTitle}</h2>
          <button onClick={onClose} aria-label="Close" className="h-9 w-9 rounded-full text-ink-soft hover:bg-surface-3">✕</button>
        </div>
        <ol className="mt-3 flex gap-2 text-xs" aria-label="Checkout steps">
          {t.coSteps.map((s, i) => (
            <li key={s} className={`flex-1 rounded-full px-2 py-1 text-center ${step > i + 1 ? "bg-good-bg text-good" : step === i + 1 ? "bg-brand text-white" : "bg-surface-3 text-ink-faint"}`}>
              {step > i + 1 ? "✓ " : ""}{s}
            </li>
          ))}
        </ol>

        {quote && (
          <div className="mt-4 rounded-2xl border border-line bg-surface-2 p-3 text-[14px]">
            <p className="font-semibold">{t.oneBillAll}</p>
            <ul className="mt-1 space-y-0.5 text-ink-soft">
              {quote.items.map((i) => <li key={i.product_id} className="flex justify-between"><span>{i.name}{i.qty > 1 ? ` × ${i.qty}` : ""}</span><span>{inr(i.unit_price * i.qty)}</span></li>)}
            </ul>
            <div className="mt-2 flex justify-between border-t border-line pt-2 font-semibold"><span>{t.monthly}</span><span>{inr(quote.total_monthly)}</span></div>
            <div className="flex justify-between text-ink-soft"><span>{t.setup}</span><span>{inr(quote.total_setup)}</span></div>
            <div className="flex justify-between text-ink-soft"><span>{t.contract}</span><span>{quote.contract_months} {t.months}</span></div>
          </div>
        )}

        {step === 1 && (
          <section className="mt-4">
            <h3 className="font-semibold">{t.signTitle} <Pill tone="warn">{t.simTag}</Pill></h3>
            <p className="mt-1 text-sm text-ink-soft">{t.signSub}</p>
            {!otpSent ? (
              <Button className="mt-3 w-full" onClick={() => setOtpSent(true)}>{t.sendOtp}</Button>
            ) : (
              <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
                setEsign(await api.post<Esign>("/checkout/esign", { session_id: sessionId, quote_id: quoteId, otp })); setStep(2);
              }); }}>
                <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" aria-label="OTP"
                  placeholder={t.otpPh} className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3 tracking-[0.3em]" />
                <Button type="submit" disabled={busy || otp.length !== 6}>{t.sign}</Button>
              </form>
            )}
            {otpSent && <p className="mt-1 text-xs text-ink-faint">{t.otpDemo}</p>}
          </section>
        )}

        {step === 2 && (
          <section className="mt-4">
            {esign && <p className="text-sm text-good">✓ {t.signed} · ref {esign.document_hash}</p>}
            <h3 className="mt-2 font-semibold">{t.apTitle} <Pill tone="warn">{t.simTag}</Pill></h3>
            <p className="mt-1 text-sm text-ink-soft">{t.apSub}</p>
            <div className="mt-3 flex gap-2" role="radiogroup" aria-label="Payment method">
              {([["upi_autopay", t.upi], ["nach", t.nach]] as const).map(([v, l]) => (
                <button key={v} role="radio" aria-checked={method === v} onClick={() => setMethod(v)}
                  className={`min-h-[44px] flex-1 rounded-xl border text-sm font-medium ${method === v ? "border-brand bg-brand-light text-ink" : "border-line-strong text-ink-soft"}`}>{l}</button>
              ))}
            </div>
            <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
              setMandate(await api.post<Mandate>("/checkout/mandate", { session_id: sessionId, quote_id: quoteId, method, handle: method === "upi_autopay" ? handle : null })); setStep(3);
            }); }}>
              {method === "upi_autopay" && (
                <input value={handle} onChange={(e) => setHandle(e.target.value.trim())} aria-label="UPI ID" placeholder="yourname@bank"
                  className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3" />
              )}
              <Button type="submit" disabled={busy || (method === "upi_autopay" && !handle.includes("@"))} className={method === "nach" ? "w-full" : ""}>
                {t.approve}
              </Button>
            </form>
          </section>
        )}

        {step === 3 && (
          <section className="mt-4 space-y-1 text-sm">
            {esign && <p className="text-good">✓ {t.signed} · ref {esign.document_hash}</p>}
            {mandate && <p className="text-good">✓ {mandate.method} {t.approved}{mandate.handle_masked ? ` (${mandate.handle_masked})` : ""} · {mandate.mandate_id}</p>}
            <p className="text-ink-soft">{t.firstDebit}</p>
            <Button className="mt-3 w-full" onClick={onDone} disabled={placing}>{t.placeOrder} →</Button>
          </section>
        )}
        <div className="mt-3"><ErrorBox error={error} /></div>
      </div>
    </div>
  );
}
