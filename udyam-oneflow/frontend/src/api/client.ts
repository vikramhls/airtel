// Thin typed client for the FastAPI backend. Every error is a Problem {code, message, fix_hint}.

export type Problem = { code: string; message: string; fix_hint?: string | null };

export class ApiError extends Error {
  problem: Problem;
  status: number;
  constructor(status: number, problem: Problem) {
    super(problem.message);
    this.problem = problem;
    this.status = status;
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, { code: "NETWORK", message: "Can't reach the server.", fix_hint: "Check your connection and try again." });
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data?.code ? data : { code: "HTTP", message: res.statusText });
  return data as T;
}

export const api = {
  get: <T>(p: string) => call<T>("GET", p),
  post: <T>(p: string, b?: unknown) => call<T>("POST", p, b ?? {}),
  patch: <T>(p: string, b: unknown) => call<T>("PATCH", p, b),
  del: <T>(p: string) => call<T>("DELETE", p),
};

// ---------------------------------------------------------------- types
export type Chip = { label: string; value: string; multi?: boolean };

export type Profile = {
  business_type: string | null; business_name: string | null; segment: string | null; city: string | null;
  city_tier: number | null; state: string | null; employees: number | null; sites: number | null;
  has_gstin: boolean | null; gstin: string | null; gstin_status: string | null; needs: string[];
  requested_products: string[]; budget_inr: number | null; current_spend_inr: number | null; current_internet: string | null;
  fibre_available: boolean | null;
};

export type LineItem = {
  product_id: string; name: string; category: string; description: string; qty: number; unit: string;
  price_min: number; price_max: number; unit_price: number; setup_inr: number; setup_each: number;
  line_term_months: number; is_addon: boolean; why: string; rules_passed: string[]; install_days: number;
};

export type Rung = {
  label: "Start" | "Grow" | "Complete"; items: LineItem[]; addons: LineItem[]; total_monthly: number;
  total_monthly_range: [number, number]; total_setup: number; contract_months: number;
  vs_current_spend: number | null; install_days: number; why: string; over_budget_by: number | null;
};

export type UnlockPath = {
  product_id: string; name: string; category: string; blocked_by: string; failed_rules: string[];
  message: string; unlock_action: string; adds_per_month: [number, number];
  alternative_product_id: string | null; alternative_name: string | null; needed: boolean;
};

export type Recommendation = {
  available: boolean; notice: string | null; segment: string | null; city_tier: number | null; ladder: Rung[];
  blocked: UnlockPath[]; unlock_summary: { headline: string | null; product_count: number; value_per_month: [number, number] } | null;
  anchor_spend: number | null; budget_advice: { note: string; over_by: number; drop: { name: string; saves: number }[] } | null;
  trace: { segment: string; rules: { product: string; passed: string[]; failed: string[] }[];
    auto_added: { product: string; name: string; reason: string }[]; pricing: { policy: string; term: number };
    anchor: number; suggested?: Record<string, string[]>; budget_swap?: { from: string; to: string } };
  handoff: boolean;
};

export type AdvisorReply = {
  reply: string; profile: Profile; missing_slots: string[]; next_slot: string | null; chips: Chip[];
  ladder: Rung[] | null; recommendation: Recommendation | null; handoff: string | null; intent: string; lang: string;
  llm_used: boolean; explanation_source?: string | null;
};

export type Quote = {
  quote_id: string; session_id: string; rung: string; term_months: number; items: LineItem[];
  total_monthly: number; total_monthly_range: [number, number]; total_setup: number; contract_months: number;
  install_days: number; changes?: { added?: string; removed?: string; reason: string }[];
  available_addons: { product_id: string; name: string; category: string; unit: string; unit_price: number; qty: number;
    setup_inr: number; needs: string[]; description: string }[];
  blocked: UnlockPath[]; expected_activation_date: string | null; vs_current_spend: number | null;
  over_budget_by: number | null; pricing_note: string;
};

export type Check = { code: string; status: "pass" | "fail"; severity: "ok" | "blocker" | "warning"; detail: string; fix_hint: string | null };
export type ExtractedField = { value: string; masked_value: string; confidence: number; label: string };
export type KycDoc = { document_id: string; doc_type: string; filename: string; extracted: Record<string, ExtractedField>;
  low_confidence: string[]; quality?: { blur?: number; readable?: boolean; owner_confirmed?: boolean }; delete_after?: string };
export type KycReport = {
  session_id: string; consent: boolean; documents: KycDoc[]; checks: Check[];
  score: { passed: number; total: number; ratio: number }; state: "green" | "amber" | "red" | "none";
  next_action: { code: string; label: string; severity: string } | null; missing_docs: string[]; ready_for_order: boolean;
  blockers?: string[]; warnings?: string[];
};

export type Stage = { key: string; label: string; status: "done" | "in_progress" | "pending" | "blocked"; expected_date: string; note?: string | null };
export type Order = {
  order_id: string; session_id: string; status: string; order_date: string; today: string; clock_days: number;
  expected_activation_date: string; paused: boolean; stages: Stage[]; current_stage: string;
  pending_action: { code: string; action: string; fix_hint: string; link: string | null; products?: string[]; options: string[] } | null;
  lines: { product_id: string; name: string; qty: number; install_days: number; monthly: number; install_date: string }[];
  monthly_total: number; notifications: { body: string; sent_at: string }[]; partner_task: { message: string } | null;
  eta_formula: string; partner_id: string | null;
};
