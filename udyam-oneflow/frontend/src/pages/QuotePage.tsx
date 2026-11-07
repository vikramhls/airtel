import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Quote } from "../api/client";
import { Banner, Button, Card, ErrorBox, Shell, Spinner, StickyBar } from "../components/ui";
import { inr, useFlow } from "../hooks/useSession";
import { useI18n } from "../i18n";

export default function QuotePage() {
  const { t } = useI18n();
  const { flow } = useFlow();
  const nav = useNavigate();
  const [q, setQ] = useState<Quote | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (flow.quoteId) api.get<Quote>(`/quote/${flow.quoteId}`).then(setQ).catch(setError);
  }, [flow.quoteId]);

  async function act(path: string, body: object) {
    setBusy(true);
    setError(null);
    try {
      const out = await api.post<Quote>(path, { quote_id: q!.quote_id, ...body });
      setQ(out);
      const changes = (out.changes || []).filter((c) => c.reason !== "you turned it on" && c.reason !== "you turned it off");
      if (changes.length) setToast(changes.map((c) => (c.added ? "Added: " : "Removed: ") + c.reason).join(" · "));
      else setToast(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (!flow.quoteId) return <Shell back="/plan"><Banner tone="info">Pick a plan first. <Link to="/plan" className="underline">Plan</Link></Banner></Shell>;
  if (!q) return <Shell back="/plan">{error ? <ErrorBox error={error} /> : <Spinner label={t.loading} />}</Shell>;

  return (
    <Shell back="/plan">
      <h1 className="text-xl font-bold">{t.quote}</h1>
      <p className="text-sm text-ink-soft">{t.quoteSub}</p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-[12px]">
        <div className="rounded-xl border border-line bg-surface p-2"><div className="text-base">🧾</div>{t.oneBill}</div>
        <div className="rounded-xl border border-line bg-surface p-2"><div className="text-base">📞</div>{t.oneSupport}</div>
        <div className="rounded-xl border border-line bg-surface p-2"><div className="text-base">🔁</div>{t.autopayAny}</div>
      </div>
      {toast && <div className="mt-3"><Banner tone="info">{toast}</Banner></div>}

      <Card className="mt-3">
        <ul className="divide-y divide-line">
          {q.items.map((i) => (
            <li key={i.product_id} className="py-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{i.name}</p>
                  <p className="text-xs text-ink-faint">{inr(i.unit_price)} {i.unit} · band {inr(i.price_min)}–{inr(i.price_max)} · {i.line_term_months} mo
                    {i.setup_inr ? ` · setup ${inr(i.setup_inr)}` : ""}</p>
                </div>
                <div className="shrink-0 text-right font-semibold">{inr(i.unit_price * i.qty)}</div>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <div className="flex items-center rounded-lg border border-line-strong" aria-label={`Quantity of ${i.name}`}>
                  <button className="h-9 w-9 text-lg" disabled={busy || i.qty <= 1} onClick={() => act("/quote/qty", { product_id: i.product_id, qty: i.qty - 1 })} aria-label="Fewer">−</button>
                  <span className="w-8 text-center text-sm">{i.qty}</span>
                  <button className="h-9 w-9 text-lg" disabled={busy} onClick={() => act("/quote/qty", { product_id: i.product_id, qty: i.qty + 1 })} aria-label="More">+</button>
                </div>
                <button className="ml-auto text-sm text-bad" disabled={busy} onClick={() => act("/quote/toggle", { product_id: i.product_id, on: false })}>{t.remove}</button>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {q.available_addons.length > 0 && (
        <Card className="mt-3">
          <h2 className="font-semibold">{t.addons}</h2>
          <ul className="mt-2 space-y-2">
            {q.available_addons.map((a) => (
              <li key={a.product_id} className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] font-medium">{a.name}</p>
                  <p className="text-xs text-ink-faint">{inr(a.unit_price)} {a.unit}{a.needs.length ? ` · ${t.needsInternet}` : ""}</p>
                </div>
                <Button variant="secondary" disabled={busy} onClick={() => act("/quote/toggle", { product_id: a.product_id, on: true })}>{t.add}</Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="mt-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{t.term}:</span>
          {[12, 24].map((m) => (
            <button key={m} disabled={busy} onClick={() => act("/quote/term", { term_months: m })}
              className={`min-h-[40px] rounded-full border px-3 ${q.term_months === m ? "border-brand bg-brand text-white" : "border-line-strong"}`}>
              {m === 12 ? t.term12 : t.term24}
            </button>
          ))}
        </div>
        <dl className="mt-3 space-y-1.5 text-[15px]">
          <div className="flex justify-between"><dt>{t.monthlyTotal}</dt><dd className="font-bold">{inr(q.total_monthly)}</dd></div>
          <div className="flex justify-between"><dt>{t.setupTotal}</dt><dd>{inr(q.total_setup)}</dd></div>
          <div className="flex justify-between"><dt>{t.contract}</dt><dd>{q.contract_months} {t.months}</dd></div>
          <div className="flex justify-between"><dt>{t.expected}</dt><dd>{q.expected_activation_date || "–"}</dd></div>
          {q.vs_current_spend && <div className="flex justify-between text-ink-soft"><dt>{t.vsToday}</dt><dd>{q.vs_current_spend}×</dd></div>}
        </dl>
        {q.over_budget_by ? <p className="mt-2 text-sm font-medium text-warn">{t.overBudget} {inr(q.over_budget_by)}</p> : null}
        <p className="mt-2 text-xs text-ink-faint">{t.whySource} {t.contractNote}</p>
      </Card>

      <label className="mt-4 flex items-start gap-3 text-[14px]">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 h-5 w-5 accent-brand" />
        <span>{t.agreeTerms}</span>
      </label>
      <div className="mt-3"><ErrorBox error={error} /></div>

      <StickyBar>
        <div className="min-w-0 flex-1">
          <div className="text-lg font-bold">{inr(q.total_monthly)}<span className="text-sm font-normal text-ink-soft">{t.perMonth}</span></div>
          <div className="text-xs text-ink-soft">+ {inr(q.total_setup)} {t.setup.toLowerCase()}</div>
        </div>
        <Button disabled={!agree || !q.items.length} onClick={() => nav("/kyc")}>{t.continueKyc} →</Button>
      </StickyBar>
    </Shell>
  );
}
