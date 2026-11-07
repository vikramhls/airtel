import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Check, type KycDoc, type KycReport, type Order, type Quote } from "../api/client";
import { Checkout } from "../components/Checkout";
import { Banner, Button, Card, ErrorBox, Pill, Shell, Spinner, StickyBar } from "../components/ui";
import { inr, isDemo, useFlow } from "../hooks/useSession";
import { fill, useI18n } from "../i18n";

const DOCS: { type: string; label: string; hint: string }[] = [
  { type: "gst", label: "GST certificate", hint: "Registration certificate (REG-06)" },
  { type: "udyam", label: "Udyam certificate", hint: "MSME registration" },
  { type: "address", label: "Address proof", hint: "Electricity bill under 90 days old" },
  { type: "signatory_id", label: "Signatory ID", hint: "ID of the person who signs" },
];
const CHECK_LABEL: Record<string, string> = {
  CONSENT_RECORDED: "Consent recorded", DOC_PRESENT_GST: "GST certificate uploaded", DOC_PRESENT_UDYAM: "Udyam certificate uploaded",
  DOC_PRESENT_ADDR: "Address proof uploaded", DOC_PRESENT_ID: "Signatory ID uploaded", DOC_QUALITY: "Photos readable", PROFILE_MATCH: "Documents match your business",
  GSTIN_FORMAT: "GSTIN format", GSTIN_CHECKSUM: "GSTIN checksum", GSTIN_REGISTRY: "GSTIN found in registry",
  GSTIN_ACTIVE: "GSTIN is active", GST_NAME_MATCH: "Name matches GST registry", GST_ADDR_MATCH: "Address matches GST registry",
  UDYAM_FORMAT: "Udyam number format", UDYAM_REGISTRY: "Udyam found in registry", UDYAM_NAME_MATCH: "Udyam name matches GST",
  UDYAM_LOCATION: "Udyam city/state match", ADDR_DATE_FRESH: "Bill is under 90 days old", ADDR_MATCHES_BUSINESS: "Bill matches business",
  ID_FORMAT: "ID number format", ID_NOT_EXPIRED: "ID not expired", ID_NAME_BUSINESS: "Signatory belongs to business",
};
const APPLICANTS = ["K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K09", "K10", "K11", "K12"];

type ConsentText = { text: string; retention_days: number; version: string };

export default function Kyc() {
  const { t } = useI18n();
  const { flow, update } = useFlow();
  const nav = useNavigate();
  const [report, setReport] = useState<KycReport | null>(null);
  const [consent, setConsent] = useState<ConsentText | null>(null);
  const [busyDoc, setBusyDoc] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [skipped, setSkipped] = useState(false);
  const [applicant, setApplicant] = useState(flow.kycApplicant || "K03");
  const [placing, setPlacing] = useState(false);
  const [checkoutOpen, setCheckout] = useState(false);
  const demo = isDemo();

  async function refresh() {
    if (!flow.sessionId) return;
    try {
      setReport(await api.get<KycReport>(`/kyc/${flow.sessionId}/report`));
    } catch (e) {
      setError(e);
    }
  }
  useEffect(() => {
    refresh();
    api.get<ConsentText>("/consent/text").then(setConsent).catch(() => undefined);
  }, [flow.sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function agree() {
    await api.post("/consent", { session_id: flow.sessionId, purpose: "kyc_verification", accepted: true });
    refresh();
  }

  async function upload(docType: string, file?: File) {
    setBusyDoc(docType);
    setError(null);
    try {
      if (file) {
        const fd = new FormData();
        fd.append("session_id", flow.sessionId!);
        fd.append("doc_type", docType);
        fd.append("file", file);
        await api.post("/kyc/upload", fd);
      } else {
        await api.post("/kyc/sample", { session_id: flow.sessionId, doc_type: docType, applicant });
      }
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusyDoc(null);
    }
  }

  async function correct(doc: KycDoc, field: string, value: string) {
    try {
      setReport(await api.patch<KycReport>(`/kyc/extraction/${doc.document_id}`, { [field]: value }));
    } catch (e) {
      setError(e);
    }
  }

  async function dropGstProducts() {
    if (!flow.quoteId) return;
    const [quote, cat] = await Promise.all([
      api.get<Quote>(`/quote/${flow.quoteId}`),
      api.get<{ products: { product_id: string; requires_gstin: boolean }[] }>("/catalogue"),
    ]);
    const gst = new Set(cat.products.filter((p) => p.requires_gstin).map((p) => p.product_id));
    let last = quote;
    for (const item of quote.items.filter((i) => gst.has(i.product_id))) {
      last = await api.post<Quote>("/quote/toggle", { quote_id: flow.quoteId, product_id: item.product_id, on: false });
    }
    alert(`Removed products that need a GSTIN. New monthly total: ${inr(last.total_monthly)}.`);
  }

  async function placeOrder() {
    if (!flow.quoteId) return nav("/plan");
    setPlacing(true);
    try {
      const o = await api.post<Order>("/orders", { session_id: flow.sessionId, quote_id: flow.quoteId });
      update({ orderId: o.order_id });
      nav(`/track/${o.order_id}`);
    } catch (e) {
      setError(e);
    } finally {
      setPlacing(false);
    }
  }

  async function deleteDocs() {
    if (!confirm("Delete all your uploaded documents now?")) return;
    await api.del(`/kyc/${flow.sessionId}/documents`);
    refresh();
  }

  if (!flow.sessionId) return <Shell back="/"><Banner tone="info">Start with the advisor first.</Banner></Shell>;
  if (!report) return <Shell back="/quote">{error ? <ErrorBox error={error} /> : <Spinner label={t.loading} />}</Shell>;

  if (!report.consent) {
    return (
      <Shell back="/quote">
        <Card>
          <h1 className="text-lg font-bold">🔒 {t.consentTitle}</h1>
          <p className="mt-2 text-[15px] leading-relaxed">{consent?.text}</p>
          <ul className="mt-3 space-y-1 text-[14px] text-ink-soft">
            <li>• {t.consentPurpose}</li>
            <li>• {t.consentWhat}</li>
            <li>• {fill(t.consentHow, { d: consent?.retention_days ?? 7 })}</li>
            <li>• {t.consentControl}</li>
          </ul>
          <div className="mt-4 flex gap-2">
            <Button onClick={agree}>{t.agree}</Button>
            <Button variant="ghost" onClick={() => setSkipped(true)}>{t.notNow}</Button>
          </div>
          {skipped && (
            <div className="mt-3"><Banner tone="info">
              {t.skippedNote}
              <button className="ml-1 font-semibold underline" onClick={placeOrder}>{t.placeAnyway}</button>
            </Banner></div>
          )}
        </Card>
        <div className="mt-3"><ErrorBox error={error} /></div>
      </Shell>
    );
  }

  const docs = new Map(report.documents.map((d) => [d.doc_type, d]));
  const fails = report.checks.filter((c) => c.status === "fail");
  const gstInactive = fails.find((c) => c.code === "GSTIN_ACTIVE");

  return (
    <Shell back="/quote">
      <div className="flex items-center gap-4">
        <ReadinessRing passed={report.score.passed} total={report.score.total} state={report.state} />
        <div>
          <h1 className="text-xl font-bold">{t.kyc}</h1>
          <p className="text-sm text-ink-soft" aria-live="polite">{report.score.passed}/{report.score.total} {t.checksPassed}</p>
          {report.next_action && <p className="mt-1 text-[14px] font-medium text-warn">{t.next} {report.next_action.label}</p>}
        </div>
      </div>

      {gstInactive && (
        <div className="mt-4"><Banner tone="warn">
          <p className="font-semibold">{gstInactive.detail}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="rounded-lg bg-surface px-3 py-2 text-sm font-semibold ring-1 ring-warn-edge"
              onClick={() => api.post("/advisor/message", { session_id: flow.sessionId, text: "talk to a human about GST help" }).then(() => alert("A partner will call you to help reactivate your GSTIN (simulated)."))}>
              {t.reactivate}
            </button>
            <button className="rounded-lg bg-surface px-3 py-2 text-sm font-semibold ring-1 ring-warn-edge" onClick={dropGstProducts}>
              {t.continueNoGst}
            </button>
          </div>
        </Banner></div>
      )}

      {demo && (
        <div className="mt-3 flex items-center gap-2 text-sm">
          <label htmlFor="appl" className="text-ink-soft">{t.sampleApplicant}</label>
          <select id="appl" value={applicant} onChange={(e) => { setApplicant(e.target.value); update({ kycApplicant: e.target.value }); }}
            className="rounded-lg border border-line-strong px-2 py-1">
            {APPLICANTS.map((a) => <option key={a}>{a}</option>)}
          </select>
          <Button variant="ghost" onClick={async () => { for (const d of DOCS) await upload(d.type).catch(() => undefined); }}>{t.useAll}</Button>
        </div>
      )}

      <DigiLocker sessionId={flow.sessionId} onFetched={refresh} />

      <div className="mt-4 space-y-3">
        {DOCS.map((d) => (
          <DocTile key={d.type} spec={d} doc={docs.get(d.type)} busy={busyDoc === d.type} onUpload={upload} onCorrect={correct}
            checks={report.checks} />
        ))}
      </div>

      <Card className="mt-4">
        <h2 className="font-semibold">{t.checksHeading}</h2>
        <ul className="mt-2 space-y-1.5">
          {report.checks.map((c) => <CheckRow key={c.code} c={c} />)}
        </ul>
      </Card>
      <div className="mt-3"><ErrorBox error={error} /></div>
      <div className="mt-4 flex flex-wrap gap-3 text-sm">
        <button className="text-bad underline" onClick={deleteDocs}>{t.deleteDocs}</button>
        <button className="text-ink-soft underline" onClick={async () => { await api.post("/consent/withdraw", { session_id: flow.sessionId }); refresh(); }}>{t.withdraw}</button>
      </div>

      <StickyBar>
        <p className="min-w-0 flex-1 text-xs text-ink-soft">
          {report.ready_for_order ? t.readyNote : t.waitNote}
        </p>
        <Button onClick={() => (flow.quoteId ? setCheckout(true) : placeOrder())} disabled={placing}>{t.placeOrder} →</Button>
      </StickyBar>
      {checkoutOpen && flow.quoteId && (
        <Checkout sessionId={flow.sessionId} quoteId={flow.quoteId} placing={placing}
          onClose={() => setCheckout(false)} onDone={placeOrder} />
      )}
    </Shell>
  );
}

function DigiLocker({ sessionId, onFetched }: { sessionId: string; onFetched: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  async function fetchDocs(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.post<{ fetched: string[]; missing: string[] }>("/kyc/digilocker", { session_id: sessionId, otp });
      setDone(`Fetched ${r.fetched.length} document${r.fetched.length === 1 ? "" : "s"}` +
        (r.missing.length ? `; not in DigiLocker: ${r.missing.join(", ")}. Upload ${r.missing.length === 1 ? "it" : "them"} below.` : "."));
      setOpen(false);
      onFetched();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="font-semibold">{t.digiTitle} <Pill tone="warn">{t.simTag}</Pill></p>
          <p className="text-xs text-ink-faint">{t.digiSub}</p>
        </div>
        {!open && <Button variant="secondary" onClick={() => setOpen(true)}>{t.fetch}</Button>}
      </div>
      {open && (
        <form className="mt-3 flex gap-2" onSubmit={fetchDocs}>
          <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric"
            aria-label="DigiLocker OTP" placeholder="OTP (demo: 123456)" className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3" />
          <Button type="submit" disabled={busy || otp.length !== 6}>{busy ? t.fetching : t.verify}</Button>
        </form>
      )}
      {done && <p className="mt-2 text-sm text-good">✓ {done}</p>}
      <div className="mt-2"><ErrorBox error={error} /></div>
    </Card>
  );
}

function ReadinessRing({ passed, total, state }: { passed: number; total: number; state: string }) {
  const r = 30, c = 2 * Math.PI * r, pct = total ? passed / total : 0;
  const color = state === "green" ? "#4ADE80" : state === "amber" ? "#FFB547" : state === "red" ? "#FF4D52" : "#86868F";
  return (
    <svg width="76" height="76" viewBox="0 0 76 76" role="img" aria-label={`${passed} of ${total} checks passed`}>
      <circle cx="38" cy="38" r={r} fill="none" stroke="#26262B" strokeWidth="8" />
      <circle cx="38" cy="38" r={r} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`} transform="rotate(-90 38 38)" />
      <text x="38" y="43" textAnchor="middle" fontSize="15" fontWeight="700" fill="#F4F4F5">{passed}/{total}</text>
    </svg>
  );
}

function CheckRow({ c }: { c: Check }) {
  const { t } = useI18n();
  const icon = c.status === "pass" ? "✓" : c.severity === "warning" ? "⚠" : "✕";
  const color = c.status === "pass" ? "text-good" : c.severity === "warning" ? "text-warn" : "text-bad";
  return (
    <li className="flex gap-2 text-[14px]">
      <span className={`w-4 shrink-0 font-bold ${color}`} aria-hidden>{icon}</span>
      <div className="min-w-0">
        <span className="font-medium">{t.checks[c.code] || CHECK_LABEL[c.code] || c.code}</span>
        {c.status === "fail" && <p className="text-[13px] text-ink-soft">{c.detail} {c.fix_hint && <b className={color}>→ {c.fix_hint}</b>}</p>}
      </div>
    </li>
  );
}

function DocTile({ spec, doc, busy, onUpload, onCorrect, checks }: {
  spec: { type: string; label: string; hint: string }; doc?: KycDoc; busy: boolean;
  onUpload: (t: string, f?: File) => void; onCorrect: (d: KycDoc, f: string, v: string) => void; checks: Check[];
}) {
  const { t } = useI18n();
  const [editing, setEditing] = useState<string | null>(null);
  const [val, setVal] = useState("");
  const unreadable = doc?.quality?.readable === false;
  const quality = checks.find((c) => c.code === "DOC_QUALITY" && c.status === "fail" && unreadable);
  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="font-semibold">{(t.docs[spec.type] || [spec.label])[0]} {doc && !unreadable && <Pill tone="good">{t.read}</Pill>} {unreadable && <Pill tone="bad">{t.blurry}</Pill>}</p>
          <p className="text-xs text-ink-faint">{(t.docs[spec.type] || [, spec.hint])[1]}</p>
        </div>
        {busy && <Spinner label={t.reading} />}
      </div>
      {quality && <p className="mt-2 text-[13px] text-bad">{quality.fix_hint}</p>}
      {doc && !unreadable && (
        <dl className="mt-2 grid grid-cols-1 gap-1 text-[13px]">
          {Object.entries(doc.extracted).map(([key, f]) => (
            <div key={key} className="flex items-start justify-between gap-2 border-b border-line py-1">
              <dt className="shrink-0 text-ink-faint">{f.label}</dt>
              {editing === key ? (
                <dd className="flex gap-1">
                  <input value={val} onChange={(e) => setVal(e.target.value)} className="w-40 rounded border border-line-strong px-2 py-1" aria-label={f.label} />
                  <button className="font-semibold text-brand-ring" onClick={() => { onCorrect(doc, key, val); setEditing(null); }}>{t.save}</button>
                </dd>
              ) : (
                <dd className="min-w-0 text-right">
                  <span className={f.value ? "" : "italic text-bad"}>{f.masked_value || t.blank}</span>{" "}
                  {f.confidence > 0 && f.confidence < 0.6 && <Pill tone="warn">{t.checkTag}</Pill>}{" "}
                  <button className="text-brand-ring" aria-label={`Edit ${f.label}`} onClick={() => { setEditing(key); setVal(f.value); }}>✎</button>
                </dd>
              )}
            </div>
          ))}
        </dl>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <label className="inline-flex min-h-[40px] cursor-pointer items-center rounded-xl border border-brand px-3 text-sm font-semibold text-brand-ring hover:bg-brand-light">
          📷 {doc ? t.reupload : t.upload}
          <input type="file" accept="image/png,image/jpeg,image/webp" capture="environment" className="sr-only"
            onChange={(e) => e.target.files?.[0] && onUpload(spec.type, e.target.files[0])} />
        </label>
        <button className="min-h-[40px] rounded-xl px-3 text-sm text-ink-soft hover:bg-surface-3" onClick={() => onUpload(spec.type)} disabled={busy}>
          {t.useSample}
        </button>
      </div>
    </Card>
  );
}
