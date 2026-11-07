// The owner's session/quote/order ids live in localStorage so a refresh never loses progress.
import { useCallback, useEffect, useState } from "react";

const KEY = "oneflow.state";

export type FlowState = { sessionId?: string; quoteId?: string; orderId?: string; partnerToken?: string; kycApplicant?: string };

function read(): FlowState {
  let state: FlowState = {};
  try {
    state = JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    state = {};
  }
  // Resume link (?sid=&quote=&order=): reopen a session on another device or for the demo video.
  const p = new URLSearchParams(window.location.search);
  if (p.get("sid")) {
    state = { ...state, sessionId: p.get("sid")!, quoteId: p.get("quote") || state.quoteId, orderId: p.get("order") || state.orderId };
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* ignore */ }
  }
  return state;
}

// One shared store for every page. Writes are synchronous, so a page can save an id and
// navigate in the same click: the next page reads the new value on mount.
let current: FlowState = read();
const listeners = new Set<(s: FlowState) => void>();

function commit(next: FlowState) {
  current = next;
  try {
    if (Object.keys(next).length) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode: state still lives in memory for this tab */
  }
  listeners.forEach((fn) => fn(next));
}

export function useFlow() {
  const [state, setState] = useState<FlowState>(current);
  useEffect(() => {
    listeners.add(setState);
    setState(current);
    return () => { listeners.delete(setState); };
  }, []);
  const update = useCallback((patch: Partial<FlowState>) => commit({ ...current, ...patch }), []);
  const reset = useCallback(() => {
    try {
      localStorage.removeItem("oneflow.chat");
    } catch {
      /* ignore */
    }
    commit({});
  }, []);
  return { flow: state, update, reset };
}

export const inr = (n: number | null | undefined) =>
  n === null || n === undefined ? "–" : "₹" + Math.round(n).toLocaleString("en-IN");

export const isDemo = () => new URLSearchParams(window.location.search).get("demo") === "1" ||
  (() => { try { return localStorage.getItem("oneflow.demo") === "1"; } catch { return false; } })();
