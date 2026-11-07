import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Order } from "../api/client";
import { Banner, Button, Card, ErrorBox, Shell, Spinner } from "../components/ui";
import { inr, isDemo } from "../hooks/useSession";
import { fill, useI18n } from "../i18n";

const DOT: Record<string, string> = {
  // In progress is calm (white + soft glow); amber is reserved for "waiting for you". Red never means "on track".
  done: "bg-good text-black", in_progress: "bg-ink text-black ring-2 ring-brand/60 shadow-glow", pending: "bg-line text-ink-faint", blocked: "bg-warn-edge text-black",
};

export default function Track() {
  const { t } = useI18n();
  const { orderId } = useParams();
  const [o, setO] = useState<Order | null>(null);
  const [error, setError] = useState<unknown>(null);
  const demo = isDemo();

  const load = useCallback(() => {
    api.get<Order>(`/orders/${orderId}`).then(setO).catch(setError);
  }, [orderId]);
  useEffect(() => {
    load();
    const id = setInterval(load, 5000);   // the owner checks here instead of calling support
    return () => clearInterval(id);
  }, [load]);

  async function act(path: string, body: object = {}) {
    try {
      setO(await api.post<Order>(path, body));
    } catch (e) {
      setError(e);
    }
  }

  if (!o) return <Shell back="/kyc">{error ? <ErrorBox error={error} /> : <Spinner label={t.loading} />}</Shell>;

  return (
    <Shell back="/kyc">
      <p className="text-sm text-ink-soft">{t.orderLbl} <span className="font-mono">{o.order_id}</span> · {inr(o.monthly_total)}/month</p>
      <h1 className="text-xl font-bold">{o.status === "activated" ? t.youreLive : t.track}</h1>
      <p className="text-[15px]">{t.expected}: <b>{o.expected_activation_date}</b>{o.paused && <span className="text-warn"> {t.paused}</span>}</p>

      {o.pending_action && (
        <div className="mt-4 rounded-2xl border-2 border-warn-edge bg-warn-bg p-4" role="alert">
          <p className="text-sm font-semibold uppercase tracking-wide text-warn">{t.pending}</p>
          <p className="mt-1 text-[16px] font-semibold">{o.pending_action.action}</p>
          <p className="mt-1 text-[14px] text-ink-soft">{o.pending_action.fix_hint}</p>
          {o.pending_action.products && <p className="mt-1 text-[13px]">{t.affects} {o.pending_action.products.join(", ")}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            {o.pending_action.link && <Link to={o.pending_action.link} className="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white">{t.fixNow}</Link>}
            {o.pending_action.options.includes("recheck_kyc") && (
              <Button variant="secondary" onClick={() => act(`/orders/${o.order_id}/resolve`, { action: "recheck_kyc" })}>{t.fixed}</Button>
            )}
            {o.pending_action.options.includes("remove_gst_products") && (
              <Button variant="secondary" onClick={() => act(`/orders/${o.order_id}/resolve`, { action: "remove_gst_products" })}>{t.removeThose}</Button>
            )}
            {o.pending_action.options.includes("reactivate_gstin") && (
              <Button variant="ghost" onClick={() => act(`/orders/${o.order_id}/resolve`, { action: "reactivate_gstin" })}>{t.reactivated}</Button>
            )}
          </div>
        </div>
      )}

      <Card className="mt-4">
        <ol className="relative space-y-4" aria-label="Order progress">
          {o.stages.map((s, i) => (
            <li key={s.key} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-bold ${DOT[s.status]}`}>
                  {s.status === "done" ? "✓" : s.status === "blocked" ? "!" : i + 1}
                </span>
                {i < o.stages.length - 1 && <span className={`mt-1 h-6 w-0.5 ${s.status === "done" ? "bg-good" : "bg-line"}`} />}
              </div>
              <div className="min-w-0 pb-1">
                <p className={`${s.status === "in_progress" ? "font-semibold text-ink" : s.status === "blocked" ? "font-medium text-warn" : "font-medium"}`}>{s.label}</p>
                <p className="text-xs text-ink-faint">
                  {s.status === "done" ? t.stDone : s.status === "blocked" ? t.stWaiting : s.status === "in_progress" ? t.stInProgress : t.stExpected} · {s.expected_date}
                </p>
                {s.note && <p className="mt-0.5 text-xs text-ink-soft">{s.note}</p>}
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <Card className="mt-3">
        <h2 className="font-semibold">{t.perProduct}</h2>
        <ul className="mt-2 space-y-1 text-[14px]">
          {o.lines.map((l) => (
            <li key={l.product_id} className="flex justify-between gap-2">
              <span>{l.name}{l.qty > 1 ? ` × ${l.qty}` : ""}</span>
              <span className="text-ink-soft">{l.install_days} {l.install_days === 1 ? t.day : t.days} · {t.by} {l.install_date}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-ink-faint">{o.eta_formula}</p>
      </Card>

      {o.bill && (
        <Card className="mt-3">
          <h2 className="flex items-center justify-between font-semibold">
            {t.singleBill} <span className="font-mono text-xs font-normal text-ink-faint">{o.bill.account_no}</span>
          </h2>
          <ul className="mt-2 space-y-1 text-[14px]">
            {o.bill.lines.map((l) => (
              <li key={l.name} className="flex justify-between gap-2"><span>{l.name}{l.qty > 1 ? ` × ${l.qty}` : ""}</span><span>{inr(l.monthly)}</span></li>
            ))}
          </ul>
          <div className="mt-2 flex justify-between border-t border-line pt-2 font-semibold"><span>{t.everyMonth}</span><span>{inr(o.bill.monthly_total)}</span></div>
          <div className="flex justify-between text-sm text-ink-soft"><span>{t.setupFirst}</span><span>{inr(o.bill.one_time_setup)}</span></div>
          <div className="flex justify-between text-sm text-ink-soft"><span>{fill(t.firstBill, { d: o.bill.first_bill_date })}</span><span>{inr(o.bill.first_bill_amount)}</span></div>
          {o.checkout?.mandate && (
            <p className="mt-2 text-sm text-good">✓ {t.paidBy} {o.checkout.mandate.method}{o.checkout.mandate.handle_masked ? ` (${o.checkout.mandate.handle_masked})` : ""}</p>
          )}
          {o.checkout?.esign && <p className="text-sm text-good">✓ {t.esigned} · ref {o.checkout.esign.document_hash}</p>}
          <div className="mt-3 rounded-xl bg-surface-3 p-3 text-sm">
            <p className="font-semibold">{t.oneSupportAll}</p>
            <p className="mt-0.5 text-ink-soft">📞 {o.bill.support.phone} · 💬 WhatsApp {o.bill.support.whatsapp}</p>
            <p className="text-ink-soft">{t.yourContact} {o.bill.support.account_manager}</p>
          </div>
          <p className="mt-2 text-xs text-ink-faint">{o.bill.note}</p>
        </Card>
      )}

      <Card className="mt-3">
        <h2 className="flex items-center justify-between font-semibold">{t.simulated} <span className="rounded bg-surface-3 px-2 py-0.5 text-[11px] font-normal">Simulated</span></h2>
        <ul className="mt-2 space-y-2">
          {o.notifications.map((n, i) => (
            <li key={i} className="max-w-[90%] rounded-2xl rounded-tl-sm bg-[#123524] text-[#D7F5E3] px-3 py-2 text-[14px]">
              {n.body}<span className="mt-0.5 block text-right text-[11px] text-ink-faint">{n.sent_at}</span>
            </li>
          ))}
        </ul>
      </Card>

      <div className="mt-4 flex items-center gap-3">
        <Button variant="secondary" onClick={() => act(`/orders/${o.order_id}/help`)}>{t.needHelp}</Button>
        {o.partner_task && <span className="text-sm text-good">{o.partner_task.message}</span>}
      </div>
      {o.status === "activated" && <div className="mt-3"><Banner tone="good">{t.allLive}</Banner></div>}

      {demo && (
        <Card className="mt-6 border-dashed">
          <p className="text-xs font-semibold uppercase text-ink-faint">Demo clock (today: {o.today}, day +{o.clock_days})</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button variant="ghost" onClick={() => act(`/admin/orders/${o.order_id}/advance`, { days: 1 })}>+1 day</Button>
            <Button variant="ghost" onClick={() => act(`/admin/orders/${o.order_id}/advance`, { to_stage: "scheduled" })}>→ scheduled</Button>
            <Button variant="ghost" onClick={() => act(`/admin/orders/${o.order_id}/advance`, { to_stage: "activated" })}>→ activated</Button>
            <Button variant="danger" onClick={() => act(`/admin/orders/${o.order_id}/fail`, { reason: "ADDRESS_PROOF_EXPIRED" })}>Inject: old bill</Button>
            <Button variant="danger" onClick={() => act(`/admin/orders/${o.order_id}/fail`, { reason: "SITE_SURVEY" })}>Inject: site survey</Button>
          </div>
        </Card>
      )}
      <div className="mt-3"><ErrorBox error={error} /></div>
    </Shell>
  );
}
