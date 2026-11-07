// Small dictionary-based i18n (EN + Hindi). Advisor replies come translated from the server.
import { createContext, useContext, useState, type ReactNode } from "react";

type Lang = "en" | "hi";

const en = {
  appName: "Udyam OneFlow",
  tagline: "Start where you are.",
  heroSub: "Tell us about your business. Get one clear monthly price, finish KYC on your phone, and track your order without calling anyone.",
  chat: "Chat with the advisor",
  gstinFirst: "Start with my GSTIN",
  gstinPlaceholder: "15-character GSTIN",
  go: "Go",
  synthetic: "Prototype on synthetic data. Fictional brand, people and identifiers.",
  typeMessage: "Type your answer…",
  send: "Send",
  showPlan: "Show my plan",
  done: "Done",
  yourPlan: "Your plan",
  perMonth: "/month",
  setup: "One-time setup",
  contract: "Contract",
  months: "months",
  liveIn: "Live in about",
  days: "days",
  vsToday: "vs what you pay today",
  whyBundle: "Why this bundle",
  unlocks: "Unlock more",
  getQuote: "Get quote for",
  term: "Commitment",
  term12: "12 months",
  term24: "24 months (lower price)",
  band: "Price band",
  fromCatalogue: "from the product catalogue",
  quote: "Your quote",
  addons: "Add more",
  monthlyTotal: "Monthly total",
  setupTotal: "One-time setup",
  expected: "Expected activation",
  agreeTerms: "I agree to the plan terms and the contract duration shown above.",
  continueKyc: "Continue to KYC",
  placeOrder: "Place order",
  consentTitle: "Before we read your documents",
  agree: "I agree",
  notNow: "Not now",
  kyc: "Smart KYC",
  checksPassed: "checks passed",
  useSample: "Use sample document",
  upload: "Upload photo",
  track: "Track your order",
  pending: "One thing needed",
  needHelp: "Need help?",
  simulated: "Simulated WhatsApp updates",
  partner: "Partner cockpit",
  back: "Back",
  edit: "Edit",
  save: "Save",
  cancel: "Cancel",
  retry: "Try again",
  loading: "Loading…",
};

const hi: typeof en = {
  appName: "उद्यम वनफ्लो",
  tagline: "जहाँ हैं, वहीं से शुरू करें।",
  heroSub: "अपने व्यवसाय के बारे में बताइए। एक साफ़ मासिक कीमत पाइए, फ़ोन पर KYC पूरा कीजिए और बिना कॉल किए ऑर्डर ट्रैक कीजिए।",
  chat: "सलाहकार से बात करें",
  gstinFirst: "मेरे GSTIN से शुरू करें",
  gstinPlaceholder: "15 अक्षर का GSTIN",
  go: "आगे",
  synthetic: "सिंथेटिक डेटा पर प्रोटोटाइप। ब्रांड, लोग और नंबर काल्पनिक हैं।",
  typeMessage: "अपना जवाब लिखें…",
  send: "भेजें",
  showPlan: "मेरा प्लान देखें",
  done: "हो गया",
  yourPlan: "आपका प्लान",
  perMonth: "/महीना",
  setup: "एक बार का सेटअप",
  contract: "कॉन्ट्रैक्ट",
  months: "महीने",
  liveIn: "लगभग",
  days: "दिन में चालू",
  vsToday: "आज के खर्च की तुलना में",
  whyBundle: "यह बंडल क्यों",
  unlocks: "और अनलॉक करें",
  getQuote: "कोटेशन लें:",
  term: "अवधि",
  term12: "12 महीने",
  term24: "24 महीने (कम कीमत)",
  band: "कीमत सीमा",
  fromCatalogue: "प्रोडक्ट कैटलॉग से",
  quote: "आपका कोटेशन",
  addons: "और जोड़ें",
  monthlyTotal: "मासिक कुल",
  setupTotal: "एक बार का सेटअप",
  expected: "अनुमानित चालू तारीख",
  agreeTerms: "मैं ऊपर दिखाई गई शर्तों और कॉन्ट्रैक्ट अवधि से सहमत हूँ।",
  continueKyc: "KYC पर जाएँ",
  placeOrder: "ऑर्डर करें",
  consentTitle: "दस्तावेज़ पढ़ने से पहले",
  agree: "मैं सहमत हूँ",
  notNow: "अभी नहीं",
  kyc: "स्मार्ट KYC",
  checksPassed: "जाँच पास",
  useSample: "सैंपल दस्तावेज़ लें",
  upload: "फ़ोटो अपलोड करें",
  track: "ऑर्डर ट्रैक करें",
  pending: "एक काम बाकी है",
  needHelp: "मदद चाहिए?",
  simulated: "सिम्युलेटेड व्हाट्सएप अपडेट",
  partner: "पार्टनर कॉकपिट",
  back: "वापस",
  edit: "बदलें",
  save: "सेव करें",
  cancel: "रद्द करें",
  retry: "फिर कोशिश करें",
  loading: "लोड हो रहा है…",
};

export type Strings = typeof en;
const dict: Record<Lang, Strings> = { en, hi };

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: Strings }>({ lang: "en", setLang: () => {}, t: en });

function readLang(): Lang {
  try {
    return (localStorage.getItem("oneflow.lang") as Lang) || "en";
  } catch {
    return "en";
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readLang);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("oneflow.lang", l);
    } catch {
      /* private mode: language just won't persist */
    }
  };
  return <Ctx.Provider value={{ lang, setLang, t: dict[lang] }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
