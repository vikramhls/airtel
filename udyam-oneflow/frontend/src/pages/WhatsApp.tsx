// Simulated WhatsApp channel: the same advisor API in a WhatsApp-style chat (WhatsApp's light theme,
// so it reads as "WhatsApp" at a glance and stands apart from the app's dark theme).
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type AdvisorReply, type Chip, type Rung } from "../api/client";
import { inr, useFlow } from "../hooks/useSession";
import { useI18n } from "../i18n";

type Msg = { from: "bot" | "me"; text: string; chips?: Chip[]; ladder?: Rung[] | null; at: string };

const WA = {
  wallpaper: "#EFEAE2", header: "#008069", inBubble: "#FFFFFF", outBubble: "#D9FDD3", accent: "#008069",
  text: "#111B21", meta: "#667781", bar: "#F0F2F5", line: "#E9EDEF", notice: "#FFF3C4",
};

function clock(i: number) {
  const m = 10 * 60 + 2 + i;   // a calm 10:02 onwards, not the wall clock
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export default function WhatsApp() {
  const { lang } = useI18n();
  const { update } = useFlow();
  const nav = useNavigate();
  const [sid, setSid] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [multi, setMulti] = useState<string[]>([]);
  const end = useRef<HTMLDivElement>(null);

  const start = useCallback(() => {
    setFailed(false);
    api.post<{ session_id: string; reply: string; chips: Chip[] }>("/session", { lang })
      .then((s) => {
        setSid(s.session_id);
        setMsgs([{ from: "bot", text: s.reply, chips: s.chips, at: clock(0) }]);
      })
      .catch(() => setFailed(true));
  }, [lang]);

  useEffect(() => { start(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function send(value: string, shown?: string) {
    if (!sid || !value.trim() || busy) return;
    setBusy(true);
    setMulti([]);
    setText("");
    setMsgs((m) => [...m, { from: "me", text: shown || value, at: clock(m.length) }]);
    try {
      const r = await api.post<AdvisorReply>("/advisor/message", { session_id: sid, text: value, lang });
      setMsgs((m) => [...m, { from: "bot", text: r.reply, chips: r.chips, ladder: r.ladder, at: clock(m.length) }]);
    } catch {
      setMsgs((m) => [...m, { from: "bot", text: "Sorry, something went wrong. Please try again.", at: clock(m.length) }]);
    } finally {
      setBusy(false);
    }
  }

  function openInApp() {
    if (!sid) return;
    update({ sessionId: sid, quoteId: undefined, orderId: undefined });
    nav("/plan");
  }

  const last = msgs[msgs.length - 1];
  const chips = last?.from === "bot" ? last.chips || [] : [];
  const isMulti = chips.some((c) => c.multi);

  return (
    <div className="flex min-h-screen flex-col" style={{ background: WA.wallpaper, color: WA.text }}>
      <header className="sticky top-0 z-10 flex items-center gap-3 px-3 py-2.5 text-white" style={{ background: WA.header }}>
        <button onClick={() => nav("/")} aria-label="Back" className="text-xl">←</button>
        <div className="grid h-9 w-9 place-items-center rounded-full bg-white text-sm font-bold" style={{ color: WA.header }}>A</div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">Accel Business <span aria-label="verified">✔</span></p>
          <p className="text-xs text-white/80">{sid ? "online · business account" : failed ? "offline" : "connecting…"}</p>
        </div>
      </header>

      <p className="mx-auto mt-3 max-w-[88%] rounded-lg px-3 py-1.5 text-center text-[12px] shadow-sm"
        style={{ background: WA.notice, color: "#54656F" }}>
        🔒 Simulated WhatsApp channel for the demo. Same advisor, same prices; nothing is sent to WhatsApp.
      </p>

      <main className="mx-auto w-full max-w-xl flex-1 space-y-2 px-3 py-3" aria-live="polite">
        {!sid && !failed && (
          <div className="flex justify-start">
            <div className="rounded-lg px-3 py-2 text-[14px] shadow-sm" style={{ background: WA.inBubble, color: WA.meta }}>typing…</div>
          </div>
        )}
        {failed && (
          <div className="rounded-lg bg-white p-3 text-center text-[14px] shadow-sm">
            <p>Can't reach the advisor. Is the server running on port 8000?</p>
            <button onClick={start} className="mt-2 rounded-full px-4 py-1.5 font-semibold text-white" style={{ background: WA.accent }}>Retry</button>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.from === "me" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 text-[14.5px] leading-snug shadow-sm"
              style={{ background: m.from === "me" ? WA.outBubble : WA.inBubble }}>
              {m.text}
              {m.ladder && (
                <div className="mt-2 overflow-hidden rounded-md border" style={{ borderColor: WA.line }}>
                  {m.ladder.map((r) => (
                    <div key={r.label} className="flex justify-between border-b px-3 py-1.5 last:border-0" style={{ borderColor: WA.line }}>
                      <span>{r.label}</span><span className="font-semibold">{inr(r.total_monthly)}/mo</span>
                    </div>
                  ))}
                  <button onClick={openInApp} className="w-full py-2 text-center font-medium" style={{ color: WA.accent }}>
                    📋 View plan & order in app
                  </button>
                </div>
              )}
              <span className="mt-1 block text-right text-[11px]" style={{ color: WA.meta }}>
                {m.at}{m.from === "me" ? <span style={{ color: "#53BDEB" }}> ✓✓</span> : ""}
              </span>
            </div>
          </div>
        ))}
        {busy && <p className="text-sm" style={{ color: WA.meta }}>typing…</p>}
        {chips.length > 0 && !busy && (
          <div className="flex flex-wrap gap-2 pt-1">
            {chips.map((c) => {
              const on = multi.includes(c.value);
              return (
                <button key={c.value}
                  onClick={() => (c.multi ? setMulti((m) => (on ? m.filter((x) => x !== c.value) : [...m, c.value])) : send(c.value, c.label))}
                  className="min-h-[36px] rounded-full border px-3 text-[13px] font-medium shadow-sm"
                  style={{ borderColor: WA.accent, color: on ? "#FFFFFF" : WA.accent, background: on ? WA.accent : "#FFFFFF" }}>
                  {c.multi && (on ? "✓ " : "+ ")}{c.label}
                </button>
              );
            })}
            {isMulti && (
              <button onClick={() => send(multi.join(", "), chips.filter((c) => multi.includes(c.value)).map((c) => c.label).join(", "))}
                disabled={!multi.length} className="min-h-[36px] rounded-full px-4 text-[13px] font-semibold text-white disabled:opacity-40"
                style={{ background: WA.accent }}>Send</button>
            )}
          </div>
        )}
        <div ref={end} />
      </main>

      <form className="sticky bottom-0 flex gap-2 px-2 py-2" style={{ background: WA.bar }}
        onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Message" aria-label="Message"
          className="min-h-[44px] min-w-0 flex-1 rounded-full border-0 px-4 shadow-sm"
          style={{ background: "#FFFFFF", color: WA.text }} />
        <button type="submit" aria-label="Send" disabled={!text.trim() || busy || !sid}
          className="grid h-11 w-11 place-items-center rounded-full text-lg text-white disabled:opacity-50" style={{ background: WA.accent }}>➤</button>
      </form>
    </div>
  );
}
