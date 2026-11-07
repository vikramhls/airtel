import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Quote, type Recommendation, type Rung, type UnlockPath } from "../api/client";
import { Banner, Button, Card, ErrorBox, Pill, Shell, Spinner, StickyBar } from "../components/ui";
import { inr, useFlow } from "../hooks/useSession";
import { useI18n } from "../i18n";

const RULE_TEXT: Record<string, string> = {
  city_tier: "sold in your city", employees: "fits your team size", sites: "fits your number of locations",
  gstin: "GST rule satisfied", segment_fit: "typical for your kind of business",
};
const BLOCK_ICON: Record<string, string> = {
  gstin_missing: "🧾", gstin_cancelled: "🧾", gstin_suspended: "🧾", employees: "👥", sites: "🏬", city_tier: "📍", dependency: "🔌",
};

export default function Plan() {
  const { t } = useI18n();
  const { flow, update } = useFlow();
  const nav = useNavigate();
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [term, setTerm] = useState(12);
  const [tab, setTab] = useState(0);
  const [why, setWhy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function load(termMonths = term) {
    if (!flow.sessionId) return;
    setError(null);
    try {
      setRec(await api.post<Recommendation>("/recommend", { session_id: flow.sessionId, term_months: termMonths }));
    } catch (e) {
      setError(e);
    }
  }
  useEffect(() => { load(); }, [flow.sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!flow.sessionId) return <Shell back="/"><Banner tone="info">Start with the advisor first. <Link className="underline" to="/">Home</Link></Banner></Shell>;
  if (error) return <Shell back="/advise"><ErrorBox error={error} onRetry={() => load()} /></Shell>;
  if (!rec) return <Shell back="/advise"><Spinner label={t.loading} /></Shell>;
  if (!rec.available || !rec.ladder.length) {
    return (
      <Shell back="/advise">
        <Banner tone="warn">{rec.notice}</Banner>
        <Button className="mt-4" onClick={() => nav("/advise")}>{t.back}</Button>
      </Shell>
    );
  }

  const rung = rec.ladder[tab];
  const prev = tab > 0 ? new Set(rec.ladder[tab - 1].items.map((i) => i.product_id)) : new Set<string>();

  async function getQuote() {
    setBusy(true);
    try {
      const q = await api.post<Quote>("/quote", { session_id: flow.sessionId, rung: rung.label, term_months: term });
      update({ quoteId: q.quote_id });
      nav("/quote");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function addGstin(gstin: string) {
    await api.post("/gstin-first", { session_id: flow.sessionId, gstin: gstin.trim().toUpperCase() });
    await load();
  }

  async function talkToPartner() {
    await api.post("/advisor/message", { session_id: flow.sessionId, text: "I want to talk to a human" }).catch(() => undefined);
    alert("A partner will call you today (simulated). They can see your plan, so you won't have to repeat yourself.");
  }

  return (
    <Shell back="/advise">
      <h1 className="text-xl font-bold">{t.yourPlan}</h1>
      <p className="text-sm text-ink-soft">Three ways to start. Every price is {t.fromCatalogue}.</p>

      <div className="mt-3 flex rounded-xl bg-surface-3 p-1" role="tablist">
        {rec.ladder.map((r, i) => (
          <button key={r.label} role="tab" aria-selected={tab === i} onClick={() => setTab(i)}
            className={`min-h-[44px] flex-1 rounded-lg text-[14px] font-semibold ${tab === i ? "bg-surface text-brand-ring shadow-card" : "text-ink-soft"}`}>
            {r.label}
            <span className="block text-[12px] font-normal">{inr(r.total_monthly)}</span>
          </button>
        ))}
      </div>

      <RungCard rung={rung} prev={prev} anchor={rec.anchor_spend} term={term} />

      <div className="mt-3 flex items-center gap-2 text-sm">
        <span className="font-medium">{t.term}:</span>
        {[12, 24].map((m) => (
          <button key={m} onClick={() => { setTerm(m); load(m); }}
            className={`min-h-[40px] rounded-full border px-3 ${term === m ? "border-brand bg-brand text-white" : "border-line-strong bg-surface"}`}>
            {m === 12 ? t.term12 : t.term24}
          </button>
        ))}
      </div>

      {rec.budget_advice && tab === 0 && <div className="mt-3"><Banner tone="warn">{rec.budget_advice.note}</Banner></div>}

      <Card className="mt-4">
        <button onClick={() => setWhy(!why)} className="flex w-full items-center justify-between text-left font-semibold" aria-expanded={why}>
          {t.whyBundle} <span>{why ? "−" : "+"}</span>
        </button>
        {why && <WhyPanel rec={rec} rung={rung} />}
      </Card>

      {rec.blocked.length > 0 && (
        <div className="mt-4">
          <h2 className="font-semibold">{t.unlocks}</h2>
          {rec.unlock_summary?.headline && <p className="mt-1 text-sm text-ink-soft">{rec.unlock_summary.headline}</p>}
          <div className="mt-2 space-y-2">
            {rec.blocked.map((u) => <UnlockCard key={u.product_id} u={u} onPartner={talkToPartner} onGstin={addGstin} />)}
          </div>
        </div>
      )}

      <StickyBar>
        <div className="min-w-0 flex-1">
          <div className="text-lg font-bold">{inr(rung.total_monthly)}<span className="text-sm font-normal text-ink-soft">{t.perMonth}</span></div>
          <div className="text-xs text-ink-soft">{rung.label} · {rung.contract_months} {t.months}</div>
        </div>
        <Button onClick={getQuote} disabled={busy}>{t.getQuote} {rung.label} →</Button>
      </StickyBar>
    </Shell>
  );
}

function RungCard({ rung, prev, anchor, term }: { rung: Rung; prev: Set<string>; anchor: number | null; term: number }) {
  const { t } = useI18n();
  const ratio = rung.vs_current_spend;
  const sameAsPrev = prev.size > 0 && rung.items.every((i) => prev.has(i.product_id));
  return (
    <Card className="mt-3">
      <div className="flex items-baseline gap-1">
        <span className="text-[32px] font-bold leading-none">{inr(rung.total_monthly)}</span>
        <span className="text-ink-soft">{t.perMonth}</span>
      </div>
      <p className="mt-1 text-xs text-ink-faint">
        {t.band} {inr(rung.total_monthly_range[0])}–{inr(rung.total_monthly_range[1])}; you pay {inr(rung.total_monthly)} on a {term}-month term.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-[13px]">
        <div className="rounded-xl bg-surface-3 p-2"><div className="font-semibold">{inr(rung.total_setup)}</div><div className="text-ink-faint">{t.setup}</div></div>
        <div className="rounded-xl bg-surface-3 p-2"><div className="font-semibold">{rung.contract_months} {t.months}</div><div className="text-ink-faint">{t.contract}</div></div>
        <div className="rounded-xl bg-surface-3 p-2"><div className="font-semibold">{rung.install_days} {t.days.split(" ")[0]}</div><div className="text-ink-faint">to go live</div></div>
      </div>
      {ratio !== null && anchor && (
        <p className={`mt-3 rounded-lg px-3 py-2 text-[14px] ${ratio <= 1.5 ? "bg-good-bg text-good" : "bg-surface-3 text-ink-soft"}`}>
          {ratio <= 1.5 ? "Starts near what you pay today: " : "More than you pay today because it adds services: "}
          <b>{ratio}×</b> of {inr(anchor)}
        </p>
      )}
      {sameAsPrev && <p className="mt-2 text-[13px] text-ink-soft">Your Start plan already covers what businesses like yours usually add at this step.</p>}
      {rung.over_budget_by ? <p className="mt-2 text-sm font-medium text-warn">Over your budget by {inr(rung.over_budget_by)}</p> : null}
      <ul className="mt-3 divide-y divide-line">
        {rung.items.map((i) => (
          <li key={i.product_id} className="py-2.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium">
                  {i.name} {i.qty > 1 && <span className="text-ink-soft">× {i.qty}</span>}{" "}
                  {i.is_addon && <Pill tone="brand">Suggested</Pill>}{" "}
                  {prev.size > 0 && !prev.has(i.product_id) && <Pill tone="good">New</Pill>}
                </p>
                <p className="mt-0.5 text-[13px] leading-snug text-ink-soft">{i.why}</p>
              </div>
              <div className="shrink-0 text-right">
                <div className="font-semibold">{inr(i.unit_price * i.qty)}</div>
                <div className="text-[11px] text-ink-faint" title={`Band ${inr(i.price_min)}–${inr(i.price_max)} per ${i.unit.replace("per ", "")}, from the catalogue`}>
                  {inr(i.unit_price)} {i.unit}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function WhyPanel({ rec, rung }: { rec: Recommendation; rung: Rung }) {
  const rules = new Map(rec.trace.rules.map((r) => [r.product, r]));
  return (
    <div className="mt-3 space-y-3 text-[14px]">
      <p>Your business was matched to the <b>{rec.trace.segment}</b> segment. Prices use the catalogue policy:
        12-month term = middle of the price band, 24 months = bottom of the band.</p>
      <ul className="space-y-2">
        {rung.items.map((i) => {
          const r = rules.get(i.product_id);
          return (
            <li key={i.product_id} className="rounded-lg bg-surface-3 p-2">
              <b>{i.name}</b>: {(r?.passed || i.rules_passed).map((x) => RULE_TEXT[x] || x).join(" · ")}
            </li>
          );
        })}
      </ul>
      {rec.trace.auto_added.map((a) => (
        <p key={a.product} className="rounded-lg bg-brand-light p-2 text-brand-ring">
          Added <b>{a.name}</b> once because {a.reason.replace(/requires one of .*/, "needs a base internet connection")}.
        </p>
      ))}
      {rec.trace.budget_swap && <p className="text-ink-soft">To keep close to your budget we used the cheapest connection that works.</p>}
      <p className="text-xs text-ink-faint">Source: product_catalogue.csv · rules engine (the AI never sets prices).</p>
    </div>
  );
}

function UnlockCard({ u, onPartner, onGstin }: { u: UnlockPath; onPartner: () => void; onGstin: (g: string) => Promise<void> }) {
  const gst = u.blocked_by.startsWith("gstin");
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [err, setErr] = useState<unknown>(null);
  return (
    <div className={`rounded-xl border p-3 ${u.needed ? "border-warn-edge bg-warn-bg" : "border-line bg-surface"}`}>
      <div className="flex items-start gap-2">
        <span className="text-lg" aria-hidden>{BLOCK_ICON[u.blocked_by] || "🔒"}</span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{u.name} {u.needed && <Pill tone="warn">You asked</Pill>}</p>
          <p className="mt-0.5 text-[14px] leading-snug">{u.message}</p>
          <p className="mt-1 text-xs text-ink-soft">Adds {inr(u.adds_per_month[0])}–{inr(u.adds_per_month[1])}/month · {u.unlock_action}</p>
          {gst ? (
            <div className="mt-2 space-y-2">
              <div className="flex flex-wrap gap-2">
                {u.blocked_by === "gstin_missing" && (
                  <button onClick={() => setOpen(!open)} className="rounded-lg bg-surface px-3 py-2 text-sm font-semibold text-brand-ring ring-1 ring-brand/40">Add GSTIN</button>
                )}
                <button onClick={onPartner} className="rounded-lg px-3 py-2 text-sm font-semibold text-brand-ring">Get GST help from a partner</button>
              </div>
              {open && (
                <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setErr(null); onGstin(value).catch(setErr); }}>
                  <input value={value} onChange={(e) => setValue(e.target.value)} maxLength={15} aria-label="GSTIN" placeholder="15-character GSTIN"
                    className="min-h-[40px] min-w-0 flex-1 rounded-lg border border-line-strong px-2 font-mono uppercase" />
                  <Button type="submit" disabled={value.trim().length !== 15}>Check</Button>
                </form>
              )}
              {err ? <ErrorBox error={err} /> : null}
            </div>
          ) : u.alternative_name ? (
            <p className="mt-2 text-sm">Closest fit today: <b>{u.alternative_name}</b></p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
