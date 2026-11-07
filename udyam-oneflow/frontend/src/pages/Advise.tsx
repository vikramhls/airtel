import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type AdvisorReply, type Chip, type Profile } from "../api/client";
import { Button, ErrorBox, Shell, StickyBar } from "../components/ui";
import { inr, useFlow } from "../hooks/useSession";
import { useI18n } from "../i18n";
import { loadChat, saveChat, type ChatMsg } from "./chatStore";

const NEED_LABEL: Record<string, string> = {
  internet: "Internet", mobile: "Mobile", billing_pos: "Billing/POS", whatsapp: "WhatsApp", sms: "SMS",
  email_cloud: "Email", security: "Security", cctv: "CCTV", telephony: "Calling/IVR", wifi: "Guest Wi-Fi",
  iot: "IoT", tracking: "Tracking", website: "Website",
};

type SpeechRec = { lang: string; start: () => void; onresult: (e: { results: { 0: { transcript: string } }[] }) => void; onend: () => void };

export default function Advise() {
  const { t, lang } = useI18n();
  const { flow, update } = useFlow();
  const nav = useNavigate();
  const [msgs, setMsgs] = useState<ChatMsg[]>(loadChat);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [hasPlan, setHasPlan] = useState(false);
  const [multi, setMulti] = useState<string[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!flow.sessionId) {
      api.post<{ session_id: string; reply: string; chips: Chip[] }>("/session", { lang, partner_token: flow.partnerToken })
        .then((s) => {
          update({ sessionId: s.session_id });
          const first = [{ role: "bot" as const, text: s.reply, chips: s.chips }];
          setMsgs(first);
          saveChat(first);
        })
        .catch(setError);
    } else {
      api.get<Profile>(`/session/${flow.sessionId}/profile`).then((p) => {
        setProfile(p);
        if (p.needs.length && p.employees !== null && p.city) {
          api.post<{ available: boolean; ladder: unknown[] }>("/recommend", { session_id: flow.sessionId })
            .then((r) => setHasPlan(r.available && r.ladder.length > 0)).catch(() => undefined);
        }
      }).catch(() => undefined);
    }
  }, [flow.sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
    saveChat(msgs);
  }, [msgs]);

  const lastChips = msgs.length && msgs[msgs.length - 1].role === "bot" ? msgs[msgs.length - 1].chips || [] : [];
  const isMulti = lastChips.some((c) => c.multi);

  async function send(value: string, shown?: string) {
    if (!value.trim() || !flow.sessionId || busy) return;
    setBusy(true);
    setError(null);
    setMulti([]);
    setMsgs((m) => [...m, { role: "user", text: shown || value }]);
    setText("");
    try {
      const r = await api.post<AdvisorReply>("/advisor/message", { session_id: flow.sessionId, text: value, lang });
      setProfile(r.profile);
      if (r.ladder) setHasPlan(true);
      setMsgs((m) => [...m, { role: "bot", text: r.reply, chips: r.chips, source: r.explanation_source }]);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  function mic() {
    const W = window as unknown as { SpeechRecognition?: new () => SpeechRec; webkitSpeechRecognition?: new () => SpeechRec };
    const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = lang === "hi" ? "hi-IN" : "en-IN";
    rec.onresult = (e) => setText(e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    setListening(true);
    rec.start();
  }
  const speechOk = typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  async function saveEdit(field: string, raw: string) {
    if (!flow.sessionId) return;
    const value: unknown = ["employees", "sites", "current_spend_inr", "budget_inr"].includes(field)
      ? (raw ? Number(raw) : null)
      : field === "has_gstin" ? raw === "yes" : field === "needs" ? raw.split(",").map((s) => s.trim()).filter(Boolean) : raw;
    try {
      const r = await api.patch<{ profile: Profile; recommendation: { available: boolean; ladder: unknown[] } }>(
        `/session/${flow.sessionId}/profile`, { [field]: value });
      setProfile(r.profile);
      if (r.recommendation.available && r.recommendation.ladder.length) setHasPlan(true);
      setEditing(null);
    } catch (e) {
      setError(e);
    }
  }

  const chips: { key: string; label: string; value: string }[] = profile ? [
    { key: "business_type", label: t.chips.business_type, value: profile.business_type || "?" },
    { key: "city", label: t.chips.city, value: profile.city || "?" },
    { key: "employees", label: t.chips.employees, value: profile.employees?.toString() || "?" },
    { key: "sites", label: t.chips.sites, value: (profile.sites || 1).toString() },
    { key: "has_gstin", label: t.chips.has_gstin, value: profile.gstin_status || (profile.has_gstin === null ? "?" : profile.has_gstin ? t.yes : t.no) },
    { key: "needs", label: t.chips.needs, value: profile.needs.length ? profile.needs.map((n) => NEED_LABEL[n] || n).join(", ") : "?" },
    { key: "current_internet", label: t.chips.current_internet, value: profile.current_internet === "None" ? t.nothingYet : profile.current_internet || "?" },
    { key: "current_spend_inr", label: t.chips.current_spend_inr, value: profile.current_spend_inr ? inr(profile.current_spend_inr) : "?" },
  ] : [];

  return (
    <Shell back="/">
      {chips.length > 0 && (
        <div className="-mx-4 mb-3 flex gap-2 overflow-x-auto px-4 pb-1" aria-label="Your details">
          {chips.map((c) => (
            <button key={c.key} onClick={() => setEditing(c.key)}
              className={`shrink-0 rounded-full border px-3 py-1.5 text-left text-[13px] ${c.value === "?" ? "border-dashed border-line-strong text-ink-faint" : "border-brand/30 bg-brand-light text-brand-ring"}`}>
              <span className="font-medium">{c.label}:</span> {c.value} <span aria-hidden>✎</span>
            </button>
          ))}
        </div>
      )}
      {editing && profile && (
        // key: a fresh editor per field, so a value typed for one chip never carries over to another
        <EditChip key={editing} field={editing} profile={profile} onSave={saveEdit} onCancel={() => setEditing(null)} />
      )}

      <div className="space-y-3" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${m.role === "user" ? "rounded-br-sm bg-brand text-white" : "rounded-bl-sm border border-line bg-surface"}`}>
              {m.text}
              {m.source === "llm" && <span className="mt-1 block text-[11px] text-ink-faint">{t.aiWorded}</span>}
            </div>
          </div>
        ))}
        {busy && <div className="text-sm text-ink-faint">…</div>}
        <div ref={endRef} />
      </div>

      {lastChips.length > 0 && !busy && (
        <div className="mt-3 flex flex-wrap gap-2">
          {lastChips.map((c) => {
            const on = multi.includes(c.value);
            return (
              <button key={c.value}
                onClick={() => (c.multi ? setMulti((m) => (on ? m.filter((x) => x !== c.value) : [...m, c.value])) : send(c.value, c.label))}
                className={`min-h-[40px] rounded-full border px-3.5 text-[14px] ${on ? "border-brand bg-brand text-white" : "border-brand/40 bg-surface text-brand-ring hover:bg-brand-light"}`}
                aria-pressed={c.multi ? on : undefined}>
                {c.multi && (on ? "✓ " : "+ ")}{c.label}
              </button>
            );
          })}
          {isMulti && (
            <Button onClick={() => send(multi.join(", "), lastChips.filter((c) => multi.includes(c.value)).map((c) => c.label).join(", "))}
              disabled={!multi.length}>{t.done}</Button>
          )}
        </div>
      )}
      <div className="mt-3"><ErrorBox error={error} /></div>

      <StickyBar>
        {hasPlan ? (
          <Button onClick={() => nav("/plan")} className="w-full">{t.showPlan} →</Button>
        ) : (
          <form className="flex w-full gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <label htmlFor="msg" className="sr-only">{t.typeMessage}</label>
            <input id="msg" value={text} onChange={(e) => setText(e.target.value)} placeholder={t.typeMessage}
              className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3 text-[15px] focus:border-brand focus:outline-none" />
            {speechOk && (
              <button type="button" onClick={mic} aria-label="Speak"
                className={`min-h-[44px] w-11 rounded-xl border ${listening ? "border-bad bg-bad-bg" : "border-line-strong"}`}>🎤</button>
            )}
            <Button type="submit" disabled={busy || !text.trim()}>{t.send}</Button>
          </form>
        )}
      </StickyBar>
      {hasPlan && (
        <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t.changeSomething}
            className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line-strong px-3 text-[15px]" />
          <Button type="submit" variant="secondary" disabled={!text.trim()}>{t.send}</Button>
        </form>
      )}
    </Shell>
  );
}

function EditChip({ field, profile, onSave, onCancel }: {
  field: string; profile: Profile; onSave: (f: string, v: string) => void; onCancel: () => void;
}) {
  const { t } = useI18n();
  const initial: Record<string, string> = {
    business_type: profile.business_type || "", city: profile.city || "", employees: profile.employees?.toString() || "",
    sites: (profile.sites || 1).toString(),
    has_gstin: profile.has_gstin === null ? "" : profile.has_gstin ? "yes" : "no",
    needs: profile.needs.join(","), current_spend_inr: profile.current_spend_inr?.toString() || "",
    current_internet: profile.current_internet || "",
  };
  const [v, setV] = useState(initial[field] ?? "");
  const numeric = ["employees", "sites", "current_spend_inr"].includes(field);
  const picked = v.split(",").filter(Boolean);
  const toggleNeed = (n: string) => setV((picked.includes(n) ? picked.filter((x) => x !== n) : [...picked, n]).join(","));
  return (
    <div className="mb-3 rounded-2xl border border-brand/30 bg-surface p-3 shadow-card">
      <label className="text-sm font-semibold" htmlFor="edit">{t.edit}: {t.editTitles[field] || field}</label>
      {field === "current_internet" ? (
        <select id="edit" value={v} onChange={(e) => setV(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-xl border border-line-strong px-3">
          <option value="" disabled>{t.choose}</option>
          {["Mobile hotspot", "Home broadband", "Business broadband", "Leased line", "Mixed per site"].map((o) => <option key={o} value={o}>{o}</option>)}
          <option value="None">{t.nothingYet}</option>
        </select>
      ) : field === "has_gstin" ? (
        <select id="edit" value={v} onChange={(e) => setV(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-xl border border-line-strong px-3">
          <option value="" disabled>{t.choose}</option>
          <option value="yes">{t.yesGstin}</option>
          <option value="no">{t.noGstin}</option>
        </select>
      ) : field === "needs" ? (
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="What you need">
          {Object.entries(NEED_LABEL).map(([key, label]) => (
            <button key={key} type="button" onClick={() => toggleNeed(key)} aria-pressed={picked.includes(key)}
              className={`min-h-[36px] rounded-full border px-3 text-[13px] ${picked.includes(key) ? "border-brand bg-brand text-white" : "border-line-strong text-ink-soft"}`}>
              {picked.includes(key) ? "✓ " : ""}{label}
            </button>
          ))}
        </div>
      ) : (
        <input id="edit" value={v} onChange={(e) => setV(numeric ? e.target.value.replace(/\D/g, "") : e.target.value)}
          inputMode={numeric ? "numeric" : "text"} autoFocus
          className="mt-1 min-h-[44px] w-full rounded-xl border border-line-strong px-3" />
      )}
      <div className="mt-2 flex gap-2">
        <Button onClick={() => onSave(field, v)} disabled={!v.trim()}>{t.save}</Button>
        <Button variant="ghost" onClick={onCancel}>{t.cancel}</Button>
      </div>
    </div>
  );
}
