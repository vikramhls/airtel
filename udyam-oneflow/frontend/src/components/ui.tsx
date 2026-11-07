// Small shared UI pieces: layout shell, buttons, cards, banners, error box.
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { ApiError } from "../api/client";
import { useI18n } from "../i18n";

export function Shell({ children, title, back }: { children: ReactNode; title?: string; back?: string }) {
  const { lang, setLang, t } = useI18n();
  const loc = useLocation();
  const steps = [
    { path: "/advise", label: "Advisor" },
    { path: "/plan", label: "Plan" },
    { path: "/quote", label: "Quote" },
    { path: "/kyc", label: "KYC" },
    { path: "/track", label: "Track" },
  ];
  const active = steps.findIndex((s) => loc.pathname.startsWith(s.path));
  return (
    <div className="min-h-screen bg-page text-ink">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-xl items-center gap-2 px-4 py-3">
          {back ? (
            <Link to={back} className="-ml-2 rounded-lg px-2 py-1 text-ink-soft hover:bg-surface-3" aria-label={t.back}>←</Link>
          ) : null}
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand text-sm font-bold text-white shadow-glow">U</span>
            <span className="text-[15px]">{title || t.appName}</span>
          </Link>
          <div className="ml-auto flex rounded-full border border-line p-0.5 text-sm" role="group" aria-label="Language">
            {(["en", "hi"] as const).map((l) => (
              <button key={l} onClick={() => setLang(l)}
                className={`min-h-[32px] rounded-full px-3 ${lang === l ? "bg-brand text-white" : "text-ink-soft"}`}>
                {l === "en" ? "EN" : "हिं"}
              </button>
            ))}
          </div>
        </div>
        {active >= 0 && (
          <ol className="mx-auto flex max-w-xl gap-1 px-4 pb-2" aria-label="Progress">
            {steps.map((s, i) => (
              <li key={s.path} className="flex-1">
                <div className={`h-1 rounded-full ${i <= active ? "bg-brand" : "bg-line"}`} />
                <span className={`mt-1 block text-[11px] ${i === active ? "font-semibold text-brand-ring" : "text-ink-faint"}`}>{s.label}</span>
              </li>
            ))}
          </ol>
        )}
      </header>
      <main className="mx-auto max-w-xl px-4 pb-28 pt-4">{children}</main>
    </div>
  );
}

export function Button({ children, onClick, variant = "primary", disabled, type = "button", className = "" }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost" | "danger";
  disabled?: boolean; type?: "button" | "submit"; className?: string;
}) {
  const styles = {
    primary: "bg-brand text-white shadow-glow hover:bg-brand-dark disabled:bg-line disabled:text-ink-faint disabled:shadow-none",
    secondary: "border border-brand text-brand-ring bg-surface hover:bg-brand-light disabled:opacity-50",
    ghost: "text-brand-ring hover:bg-brand-light",
    danger: "border border-bad text-bad bg-surface hover:bg-bad-bg",
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`min-h-[44px] rounded-xl px-4 py-2 text-[15px] font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-ring ${styles} ${className}`}>
      {children}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-surface p-4 shadow-card ${className}`}>{children}</section>;
}

export function Banner({ tone, children }: { tone: "info" | "warn" | "bad" | "good"; children: ReactNode }) {
  const cls = {
    info: "bg-brand-light border-brand/30 text-brand-ring",
    warn: "bg-warn-bg border-warn-edge text-warn",
    bad: "bg-bad-bg border-bad/30 text-bad",
    good: "bg-good-bg border-good/30 text-good",
  }[tone];
  return <div className={`rounded-xl border px-3 py-2 text-[14px] leading-snug ${cls}`}>{children}</div>;
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  if (!error) return null;
  const p = error instanceof ApiError ? error.problem : { message: String(error), fix_hint: null };
  return (
    <div role="alert" className="rounded-xl border border-bad/30 bg-bad-bg p-3 text-[14px] text-bad">
      <p className="font-semibold">{p.message}</p>
      {p.fix_hint && <p className="mt-1">{p.fix_hint}</p>}
      {onRetry && <button onClick={onRetry} className="mt-2 font-semibold underline">{t.retry}</button>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-ink-soft" role="status" aria-live="polite">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function StickyBar({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/90 backdrop-blur">
      <div className="mx-auto flex max-w-xl items-center gap-3 px-4 py-3">{children}</div>
    </div>
  );
}

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "brand" | "warn" | "good" | "bad" }) {
  const cls = {
    neutral: "bg-surface-3 text-ink-soft",
    brand: "bg-brand-light text-brand-ring",
    warn: "bg-warn-bg text-warn",
    good: "bg-good-bg text-good",
    bad: "bg-bad-bg text-bad",
  }[tone];
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}
