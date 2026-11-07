import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { Banner, Button, Card, ErrorBox, Pill, Shell, Spinner } from "../components/ui";
import { inr } from "../hooks/useSession";

// Chart colours validated with the dataviz palette checker (dark surface): all checks pass.
const C = { main: "#F0383E", muted: "#5A2326", base: "#4A90C2", grid: "#26262B", axis: "#86868F", ink: "#F4F4F5" };
const SEGMENTS = ["", "Micro retail & services", "Professional offices", "Small multi-site businesses", "Small manufacturers"];
const ACTIONS = ["", "Assisted visit", "Self-serve link", "GST help first", "Call now", "WhatsApp link, not call"];
const ACTION_TONE: Record<string, "brand" | "warn" | "good" | "neutral"> = {
  "Assisted visit": "brand", "Self-serve link": "good", "GST help first": "warn", "Call now": "neutral", "WhatsApp link, not call": "neutral",
};

type Funnel = { stages: { stage: string; count: number; pct_of_previous: number | null }[]; lead_to_activation_pct: number;
  avg_days_to_activate: number; avg_follow_up_calls: number; cac_per_activation_inr: number };
type Drops = { total_dropped: number; rows: { stage: string; reason: string; count: number; pct_of_drops: number }[]; top3: { reason: string }[] };
type Source = { source: string; leads: number; activation_pct: number; cost_per_lead_inr: number; cac_per_activation_inr: number | null };
type Lead = { lead_id: string; business_name: string; segment: string; city: string; lead_source: string; propensity: number;
  expected_annual_value_inr: number; pred_mrr_inr: number; action: string; reasons: string[]; stage_reached: string; outcome: string; drop_reason: string };
type Handoff = { id: number; session_id: string; reason: string; created_at: string; summary: string[];
  score: { score: number; routing: string; expected_annual_value_inr: number; reasons: { feature: string; effect: string }[] } | null };
type Sim = { baseline: Record<string, number> & { funnel: number[] }; projected: Record<string, number> & { funnel: number[] }; stages: string[];
  by_reason: { reason: string; lever: string; stage: string; leads: number; rate: number; recovered: number; extra_activations: number }[];
  sensitivity: Record<string, { activations: number; cac_inr: number; lead_to_activation_pct: number }>; formulas: Record<string, string>;
  disclaimer: string; assumptions: { digital_cost_per_recovered_lead_inr: number } };
type Model = { cv_5fold: Record<string, { roc_auc_mean: number; pr_auc_mean: number }>; oof_blended_auc: number; base_rate: number;
  lift_by_quintile: { quintile: string; mean: number; size: number }[]; mrr_regression: { cv_r2_log: number; cv_mae_inr: number }; notes: string };

const TABS = ["Overview", "Leads", "Advisor handoffs", "Simulator", "Model & links"] as const;

export default function Partner() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  return (
    <Shell title="Partner cockpit" back="/">
      <p className="text-sm text-ink-soft">Self-serve for what's easy, partners for what's hard. Data: 5,000 synthetic leads (Apr–Jun 2026).</p>
      <div className="-mx-4 mt-3 flex gap-1 overflow-x-auto px-4" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`min-h-[40px] shrink-0 rounded-full px-3 text-sm font-medium ${tab === t ? "bg-brand text-white" : "bg-surface text-ink-soft ring-1 ring-line"}`}>{t}</button>
        ))}
      </div>
      <div className="mt-4">
        {tab === "Overview" && <Overview />}
        {tab === "Leads" && <Leads />}
        {tab === "Advisor handoffs" && <Handoffs />}
        {tab === "Simulator" && <Simulator />}
        {tab === "Model & links" && <ModelLinks />}
      </div>
    </Shell>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-3">
      <div className="text-[12px] text-ink-faint">{label}</div>
      <div className="text-xl font-bold text-ink">{value}</div>
      {sub && <div className="text-[12px] text-ink-soft">{sub}</div>}
    </div>
  );
}

function useLoad<T>(path: string, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    setData(null);
    api.get<T>(path).then(setData).catch(setError);
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error };
}

const SHORT: Record<string, string> = {
  Lead: "Lead", Contacted: "Contact", "Needs assessed": "Needs", "Quote accepted": "Quote", "KYC complete": "KYC", Activated: "Live",
};
const tooltipStyle = { borderRadius: 10, border: "1px solid #3A3A41", fontSize: 13, background: "#141416", color: "#F4F4F5" };

function Overview() {
  const [segment, setSegment] = useState("");
  const q = segment ? `?segment=${encodeURIComponent(segment)}` : "";
  const funnel = useLoad<Funnel>(`/analytics/funnel${q}`, [segment]);
  const drops = useLoad<Drops>(`/analytics/dropreasons${q}`, [segment]);
  const sources = useLoad<Source[]>("/analytics/sources");
  const [table, setTable] = useState(false);

  const dropData = useMemo(() => {
    if (!drops.data) return [];
    const agg = new Map<string, number>();
    drops.data.rows.forEach((r) => agg.set(r.reason, (agg.get(r.reason) || 0) + r.count));
    return [...agg.entries()].map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count).slice(0, 10);
  }, [drops.data]);
  const top3 = new Set(dropData.slice(0, 3).map((d) => d.reason));

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <label htmlFor="seg" className="text-sm text-ink-soft">Segment</label>
        <select id="seg" value={segment} onChange={(e) => setSegment(e.target.value)} className="min-h-[40px] rounded-lg border border-line-strong px-2 text-sm">
          {SEGMENTS.map((s) => <option key={s} value={s}>{s || "All segments"}</option>)}
        </select>
      </div>
      {funnel.data ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Lead → activation" value={`${funnel.data.lead_to_activation_pct}%`} />
            <Stat label="CAC per activation" value={inr(funnel.data.cac_per_activation_inr)} />
            <Stat label="Days to activate" value={`${funnel.data.avg_days_to_activate}`} sub="average, activated leads" />
            <Stat label="Status-chase calls" value={`${funnel.data.avg_follow_up_calls}`} sub="per activated customer" />
          </div>
          <Card>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Funnel (leads reaching each stage)</h2>
              <button className="text-xs text-brand-ring underline" onClick={() => setTable(!table)}>{table ? "Chart" : "Table"}</button>
            </div>
            {table ? (
              <table className="mt-2 w-full text-sm">
                <thead><tr className="text-left text-ink-faint"><th>Stage</th><th className="text-right">Leads</th><th className="text-right">% of previous</th></tr></thead>
                <tbody>{funnel.data.stages.map((s) => <tr key={s.stage}><td>{s.stage}</td><td className="text-right">{s.count.toLocaleString("en-IN")}</td><td className="text-right">{s.pct_of_previous ?? "–"}</td></tr>)}</tbody>
              </table>
            ) : (
              <div className="mt-2 h-60">
                <ResponsiveContainer>
                  <BarChart data={funnel.data.stages} margin={{ top: 18, right: 4, left: -12, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke={C.grid} />
                    <XAxis dataKey="stage" tick={{ fontSize: 11, fill: C.axis }} interval={0} tickFormatter={(s: string) => SHORT[s] || s} />
                    <YAxis tick={{ fontSize: 11, fill: C.axis }} />
                    <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} labelStyle={{ color: "#F4F4F5" }} itemStyle={{ color: "#F4F4F5" }} contentStyle={tooltipStyle} formatter={(v: number, _n, p) => [`${v.toLocaleString("en-IN")} leads (${p.payload.pct_of_previous ?? 100}% of previous)`, p.payload.stage]} />
                    <Bar isAnimationActive={false} dataKey="count" fill={C.main} radius={[4, 4, 0, 0]} maxBarSize={36}>
                      <LabelList dataKey="pct_of_previous" position="top" formatter={(v: number | null) => (v ? `${v}%` : "")} style={{ fontSize: 11, fill: C.ink }} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </>
      ) : <Spinner label="Loading funnel…" />}

      <Card>
        <h2 className="font-semibold">Why leads drop (top 10, top 3 highlighted)</h2>
        <p className="text-xs text-ink-faint">{drops.data?.total_dropped.toLocaleString("en-IN")} dropped leads</p>
        {dropData.length > 0 && (
          <div className="mt-2" style={{ height: dropData.length * 30 + 20 }}>
            <ResponsiveContainer>
              <BarChart data={dropData} layout="vertical" margin={{ top: 0, right: 36, left: 0, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={C.grid} />
                <XAxis type="number" tick={{ fontSize: 11, fill: C.axis }} />
                <YAxis type="category" dataKey="reason" width={150} tick={{ fontSize: 10.5, fill: C.ink }} />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} labelStyle={{ color: "#F4F4F5" }} itemStyle={{ color: "#F4F4F5" }} contentStyle={tooltipStyle} formatter={(v: number) => [`${v} leads`, "Dropped"]} />
                <Bar isAnimationActive={false} dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={18}>
                  {dropData.map((d) => <Cell key={d.reason} fill={top3.has(d.reason) ? C.main : C.muted} />)}
                  <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: C.ink }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {sources.data && (
        <Card>
          <h2 className="font-semibold">Lead sources</h2>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead><tr className="text-left text-ink-faint"><th>Source</th><th className="text-right">Leads</th><th className="text-right">Activation</th><th className="text-right">Cost/lead</th><th className="text-right">CAC</th></tr></thead>
              <tbody>{sources.data.map((s) => (
                <tr key={s.source} className="border-t border-line"><td className="py-1.5">{s.source}</td><td className="text-right">{s.leads}</td>
                  <td className="text-right">{s.activation_pct}%</td><td className="text-right">{inr(s.cost_per_lead_inr)}</td><td className="text-right">{inr(s.cac_per_activation_inr)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      )}
      <ErrorBox error={funnel.error || drops.error || sources.error} />
    </div>
  );
}

function Leads() {
  const [segment, setSegment] = useState("");
  const [action, setAction] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const params = new URLSearchParams({ limit: "40", open_only: "true", min_score: String(minScore) });
  if (segment) params.set("segment", segment);
  if (action) params.set("action", action);
  const { data, error } = useLoad<{ total: number; rows: Lead[]; note: string }>(`/partner/leads?${params}`, [segment, action, minScore]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select aria-label="Segment" value={segment} onChange={(e) => setSegment(e.target.value)} className="min-h-[40px] rounded-lg border border-line-strong px-2">
          {SEGMENTS.map((s) => <option key={s} value={s}>{s || "All segments"}</option>)}
        </select>
        <select aria-label="Action" value={action} onChange={(e) => setAction(e.target.value)} className="min-h-[40px] rounded-lg border border-line-strong px-2">
          {ACTIONS.map((s) => <option key={s} value={s}>{s || "All actions"}</option>)}
        </select>
        <label className="flex items-center gap-1">Score ≥
          <input type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="w-16 rounded-lg border border-line-strong px-2 py-1.5" />
        </label>
      </div>
      {data ? (
        <>
          <p className="text-xs text-ink-faint">{data.total.toLocaleString("en-IN")} open leads, sorted by expected annual value. {data.note}</p>
          <ul className="space-y-2">
            {data.rows.map((l) => (
              <li key={l.lead_id}>
                <button onClick={() => api.get<Record<string, unknown>>(`/partner/leads/${l.lead_id}`).then(setDetail)}
                  className="w-full rounded-2xl border border-line bg-surface p-3 text-left hover:border-brand/40">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{l.business_name}</p>
                      <p className="text-xs text-ink-faint">{l.lead_id} · {l.city} · {l.lead_source} · stopped at {l.stage_reached}</p>
                    </div>
                    <ScoreChip score={l.propensity} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <Pill tone={ACTION_TONE[l.action]}>{l.action}</Pill>
                    <span className="text-xs text-ink-soft">EV {inr(l.expected_annual_value_inr)}/yr · {l.reasons.join(" · ")}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : error ? <ErrorBox error={error} /> : <Spinner label="Scoring leads…" />}
      {detail && (
        <div className="fixed inset-0 z-30 flex items-end bg-black/60" onClick={() => setDetail(null)}>
          <div className="mx-auto w-full max-w-xl rounded-t-2xl bg-surface p-4" onClick={(e) => e.stopPropagation()}>
            <p className="text-lg font-bold">{String(detail.business_name)}</p>
            <p className="text-sm text-ink-soft">{String(detail.lead_id)} · score {String(detail.propensity)} · predicted {inr(detail.pred_mrr_inr as number)}/month</p>
            <Banner tone="info"><b>Suggested next action:</b> {String(detail.next_action)}</Banner>
            <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-surface-3 p-2 text-xs">{JSON.stringify(detail.profile, null, 1)}</pre>
            <Button className="mt-3 w-full" onClick={() => setDetail(null)}>Close</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreChip({ score }: { score: number }) {
  const tone = score >= 12 ? "bg-good-bg text-good" : score >= 6 ? "bg-brand-light text-brand-ring" : "bg-surface-3 text-ink-soft";
  return <span className={`shrink-0 rounded-lg px-2 py-1 text-sm font-bold ${tone}`} title="Activation propensity (0-100), out-of-fold">{score.toFixed(1)}</span>;
}

function Handoffs() {
  const { data, error } = useLoad<Handoff[]>("/partner/handoffs");
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Spinner label="Loading…" />;
  if (!data.length) return <Banner tone="info">No open handoffs. When the advisor can't close (city not served, owner asks for a person, large or custom needs) the case lands here with a 3-line summary.</Banner>;
  return (
    <ul className="space-y-2">
      {data.map((h) => (
        <li key={h.id}><Card>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 text-[14px]">
              {h.summary.map((s, i) => <p key={i} className={i === 0 ? "font-medium" : "text-ink-soft"}>{s}</p>)}
              <p className="mt-1 text-xs text-ink-faint">{h.session_id} · {h.created_at}</p>
            </div>
            {h.score && <ScoreChip score={h.score.score} />}
          </div>
          {h.score && <p className="mt-2 text-xs text-ink-soft">Model says: <b>{h.score.routing}</b> · {h.score.reasons.map((r) => `${r.feature} (${r.effect})`).join(", ")}</p>}
        </Card></li>
      ))}
    </ul>
  );
}

function Simulator() {
  const [defaults, setDefaults] = useState<{ recovery: Record<string, number>; levers: Record<string, string> } | null>(null);
  const [recovery, setRecovery] = useState<Record<string, number>>({});
  const [days, setDays] = useState(4);
  const [sim, setSim] = useState<Sim | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.get<{ recovery: Record<string, number>; levers: Record<string, string> }>("/simulate/defaults").then((d) => {
      setDefaults(d);
      setRecovery(d.recovery);
    }).catch(setError);
  }, []);
  useEffect(() => {
    if (!defaults) return;
    const id = setTimeout(() => api.post<Sim>("/simulate", { recovery, days_saved_digital: days }).then(setSim).catch(setError), 250);
    return () => clearTimeout(id);
  }, [recovery, days, defaults]);

  if (error) return <ErrorBox error={error} />;
  if (!defaults || !sim) return <Spinner label="Running simulation…" />;
  const chart = sim.stages.map((s, i) => ({ stage: s, Baseline: sim.baseline.funnel[i], Projected: Math.round(sim.projected.funnel[i]) }));

  return (
    <div className="space-y-4">
      <Banner tone="warn">{sim.disclaimer}</Banner>
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Activations" value={`${sim.baseline.activations} → ${Math.round(sim.projected.activations)}`} sub={`range ${Math.round(sim.sensitivity.low.activations)}–${Math.round(sim.sensitivity.high.activations)}`} />
        <Stat label="Lead → activation" value={`${sim.baseline.lead_to_activation_pct}% → ${sim.projected.lead_to_activation_pct}%`} />
        <Stat label="Blended CAC" value={`${inr(sim.baseline.cac_inr)} → ${inr(sim.projected.cac_inr)}`} sub={`range ${inr(sim.sensitivity.high.cac_inr)}–${inr(sim.sensitivity.low.cac_inr)}`} />
        <Stat label="Needs → quote" value={`${sim.baseline.assessed_to_quote_pct}% → ${sim.projected.assessed_to_quote_pct}%`} />
      </div>
      <Card>
        <h2 className="font-semibold">Funnel: observed vs projected</h2>
        <div className="mt-2 h-60">
          <ResponsiveContainer>
            <BarChart data={chart} margin={{ top: 8, right: 4, left: -12, bottom: 0 }} barGap={2}>
              <CartesianGrid vertical={false} stroke={C.grid} />
              <XAxis dataKey="stage" tick={{ fontSize: 11, fill: C.axis }} interval={0} tickFormatter={(s: string) => SHORT[s] || s} />
              <YAxis tick={{ fontSize: 11, fill: C.axis }} />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} labelStyle={{ color: "#F4F4F5" }} itemStyle={{ color: "#F4F4F5" }} contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12, color: C.ink }} />
              <Bar isAnimationActive={false} dataKey="Baseline" fill={C.base} radius={[4, 4, 0, 0]} maxBarSize={22} />
              <Bar isAnimationActive={false} dataKey="Projected" fill={C.main} radius={[4, 4, 0, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <h2 className="font-semibold">Assumptions (editable)</h2>
        <p className="text-xs text-ink-faint">Share of each drop reason OneFlow recovers. Recovered leads then convert like their own segment did.</p>
        <label className="mt-3 flex items-center gap-2 text-sm">Days saved by the digital path
          <input type="range" min={0} max={10} value={days} onChange={(e) => setDays(Number(e.target.value))} className="flex-1 accent-brand" /> <b>{days}</b>
        </label>
        <ul className="mt-3 space-y-2">
          {Object.entries(recovery).map(([reason, rate]) => {
            const row = sim.by_reason.find((r) => r.reason === reason);
            return (
              <li key={reason} className="text-[13px]">
                <div className="flex justify-between gap-2"><span>{reason}</span><b>{Math.round(rate * 100)}%</b></div>
                <input type="range" min={0} max={100} step={5} value={Math.round(rate * 100)} aria-label={reason}
                  onChange={(e) => setRecovery((r) => ({ ...r, [reason]: Number(e.target.value) / 100 }))} className="w-full accent-brand" />
                <div className="text-[11px] text-ink-faint">{defaults.levers[reason]}{row ? ` · +${row.extra_activations} activations` : ""}</div>
              </li>
            );
          })}
        </ul>
        <Button variant="ghost" className="mt-2" onClick={() => { setRecovery(defaults.recovery); setDays(4); }}>Reset to defaults</Button>
      </Card>
      <Card>
        <h2 className="font-semibold">How it's computed</h2>
        <ul className="mt-1 space-y-1 text-[13px] text-ink-soft">
          {Object.entries(sim.formulas).map(([k, v]) => <li key={k}><b>{k}:</b> {v}</li>)}
          <li><b>digital cost per recovered lead:</b> {inr(sim.assumptions.digital_cost_per_recovered_lead_inr)} (dataset Website-form cost per lead)</li>
        </ul>
      </Card>
    </div>
  );
}

function ModelLinks() {
  const { data, error } = useLoad<Model>("/analytics/model");
  const [partnerId, setPartnerId] = useState("PARTNER-RAVI");
  const [link, setLink] = useState<string | null>(null);
  const lift = data?.lift_by_quintile.map((q) => ({ q: q.quintile, rate: Math.round(q.mean * 1000) / 10 })) || [];
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold">Create a tracked link</h2>
        <p className="text-xs text-ink-faint">Anything the owner buys from this link is credited to you, even when they finish on their own.</p>
        <div className="mt-2 flex gap-2">
          <input value={partnerId} onChange={(e) => setPartnerId(e.target.value)} aria-label="Partner ID" className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3" />
          <Button onClick={() => api.post<{ url: string }>("/partner/links", { partner_id: partnerId }).then((r) => setLink(window.location.origin + r.url))}>Create</Button>
        </div>
        {link && <p className="mt-2 break-all rounded-lg bg-brand-light p-2 text-sm text-brand-ring">{link}</p>}
      </Card>
      {data ? (
        <Card>
          <h2 className="font-semibold">Propensity model (trained on lead-time fields only)</h2>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Stat label="ROC-AUC (5-fold, logistic)" value={data.cv_5fold.lr.roc_auc_mean.toFixed(3)} />
            <Stat label="Out-of-fold blended AUC" value={data.oof_blended_auc.toFixed(3)} />
            <Stat label="Base activation rate" value={`${(data.base_rate * 100).toFixed(1)}%`} />
            <Stat label="MRR model R² (log)" value={data.mrr_regression.cv_r2_log.toFixed(2)} sub={`MAE ${inr(data.mrr_regression.cv_mae_inr)}`} />
          </div>
          <h3 className="mt-4 text-sm font-semibold">Activation rate by score quintile (Q5 = highest scores)</h3>
          <div className="mt-2 h-48">
            <ResponsiveContainer>
              <BarChart data={lift} margin={{ top: 18, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={C.grid} />
                <XAxis dataKey="q" tick={{ fontSize: 11, fill: C.axis }} />
                <YAxis tick={{ fontSize: 11, fill: C.axis }} unit="%" />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} labelStyle={{ color: "#F4F4F5" }} itemStyle={{ color: "#F4F4F5" }} contentStyle={tooltipStyle} formatter={(v: number) => [`${v}% activated`, "Rate"]} />
                <Bar isAnimationActive={false} dataKey="rate" fill={C.main} radius={[4, 4, 0, 0]} maxBarSize={36}>
                  <LabelList dataKey="rate" position="top" formatter={(v: number) => `${v}%`} style={{ fontSize: 11, fill: C.ink }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-ink-soft">{data.notes}</p>
        </Card>
      ) : error ? <ErrorBox error={error} /> : <Spinner label="Loading…" />}
    </div>
  );
}
