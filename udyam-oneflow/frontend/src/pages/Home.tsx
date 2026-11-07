import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Chip } from "../api/client";
import { Button, Card, ErrorBox, Shell } from "../components/ui";
import { useFlow } from "../hooks/useSession";
import { useI18n } from "../i18n";
import { saveChat, type ChatMsg } from "./chatStore";

type SessionOut = { session_id: string; reply: string; chips: Chip[]; partner_id: string | null };
type GstinOut = { registry: { trade_name: string; status: string; gstin_masked: string; state: string };
  warning: string | null; question: string | null; chips: Chip[]; profile: { city: string | null } };

export default function Home() {
  const { t, lang } = useI18n();
  const { flow, update, reset } = useFlow();
  const nav = useNavigate();
  const [gstin, setGstin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const partner = params.get("partner");
    if (partner && partner !== flow.partnerToken) {
      reset();
      update({ partnerToken: partner });
    }
    if (params.get("demo") === "1") {
      try { localStorage.setItem("oneflow.demo", "1"); } catch { /* ignore */ }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function newSession(): Promise<SessionOut> {
    const s = await api.post<SessionOut>("/session", { lang, partner_token: flow.partnerToken });
    update({ sessionId: s.session_id, quoteId: undefined, orderId: undefined });
    return s;
  }

  async function startChat() {
    setBusy(true);
    setError(null);
    try {
      const s = await newSession();
      saveChat([{ role: "bot", text: s.reply, chips: s.chips }]);
      nav("/advise");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function startGstin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await newSession();
      const g = await api.post<GstinOut>("/gstin-first", { session_id: s.session_id, gstin: gstin.trim().toUpperCase() });
      const msgs: ChatMsg[] = [
        { role: "user", text: g.registry.gstin_masked },
        { role: "bot", text: `Found ${g.registry.trade_name} (${g.profile.city || g.registry.state}). GST status: ${g.registry.status}.` +
            (g.warning ? " " + g.warning : "") + (g.question ? " " + g.question : ""), chips: g.chips },
      ];
      saveChat(msgs);
      nav("/advise");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <div className="relative pt-4">
        <div aria-hidden className="pointer-events-none absolute -top-10 left-1/2 h-56 w-72 -translate-x-1/2 rounded-full bg-brand-glow/25 blur-3xl" />
        <p className="relative text-sm font-semibold uppercase tracking-[0.2em] text-brand-ring">Accel Business</p>
        <h1 className="relative mt-1 text-[30px] font-extrabold leading-tight [text-shadow:0_0_24px_rgba(255,42,51,0.45)]">{t.tagline}</h1>
        <p className="mt-3 text-[16px] leading-relaxed text-ink-soft">{t.heroSub}</p>
        {flow.partnerToken && (
          <p className="mt-3 rounded-lg bg-brand-light px-3 py-2 text-sm text-brand-ring">
            You were invited by an Accel partner. They are credited for anything you buy here.
          </p>
        )}
      </div>

      <div className="mt-6 space-y-3">
        <Button onClick={startChat} disabled={busy} className="w-full text-[16px]">{t.chat} →</Button>
        <Card>
          <form onSubmit={startGstin} className="space-y-2">
            <label htmlFor="gstin" className="block text-[15px] font-semibold">{t.gstinFirst}</label>
            <p className="text-sm text-ink-soft">We fill in your business name, city and GST status from the (mock) registry.</p>
            <div className="flex gap-2">
              <input id="gstin" value={gstin} onChange={(e) => setGstin(e.target.value)} maxLength={15}
                placeholder={t.gstinPlaceholder} autoComplete="off"
                className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3 font-mono uppercase tracking-wider focus:border-brand focus:outline-none" />
              <Button type="submit" disabled={busy || gstin.trim().length !== 15}>{t.go}</Button>
            </div>
          </form>
        </Card>
        <ErrorBox error={error} />
      </div>

      {flow.sessionId && (
        <Card className="mt-4">
          <p className="text-sm text-ink-soft">Pick up where you left off</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Link to="/advise" className="rounded-lg bg-surface-3 px-3 py-2 text-sm font-medium">Advisor</Link>
            <Link to="/plan" className="rounded-lg bg-surface-3 px-3 py-2 text-sm font-medium">Plan</Link>
            {flow.quoteId && <Link to="/quote" className="rounded-lg bg-surface-3 px-3 py-2 text-sm font-medium">Quote</Link>}
            <Link to="/kyc" className="rounded-lg bg-surface-3 px-3 py-2 text-sm font-medium">KYC</Link>
            {flow.orderId && <Link to={`/track/${flow.orderId}`} className="rounded-lg bg-surface-3 px-3 py-2 text-sm font-medium">Track</Link>}
            <button onClick={reset} className="rounded-lg px-3 py-2 text-sm text-bad">Start over</button>
          </div>
        </Card>
      )}

      <div className="mt-8 grid grid-cols-3 gap-2 text-center text-[13px] text-ink-soft">
        <div className="rounded-xl bg-surface p-3 shadow-card"><div className="text-lg">💬</div>Plan in 2 minutes</div>
        <div className="rounded-xl bg-surface p-3 shadow-card"><div className="text-lg">📄</div>KYC on your phone</div>
        <div className="rounded-xl bg-surface p-3 shadow-card"><div className="text-lg">📍</div>Track, no calls</div>
      </div>
      <p className="mt-8 text-center text-xs text-ink-faint">{t.synthetic}</p>
      <p className="mt-2 text-center text-xs"><Link to="/partner" className="text-brand-ring underline">{t.partner}</Link></p>
    </Shell>
  );
}
