import type { Chip } from "../api/client";

export type ChatMsg = { role: "bot" | "user"; text: string; chips?: Chip[]; source?: string | null };

const KEY = "oneflow.chat";

export function loadChat(): ChatMsg[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function saveChat(msgs: ChatMsg[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(msgs.slice(-60)));
  } catch {
    /* ignore */
  }
}
