import type { HistoryItem } from "@/store/useSummarizerStore";

const HISTORY_KEY = "aitv_history_v1";
const ITEM_KEY = (id: string) => `aitv_job_${id}_v1`;

export function safeJsonParse<T>(value: string | null): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export function loadHistoryFromLocalStorage(): HistoryItem[] {
  if (typeof window === "undefined") return [];
  const arr = safeJsonParse<HistoryItem[]>(localStorage.getItem(HISTORY_KEY));
  return Array.isArray(arr) ? arr : [];
}

export function saveHistoryToLocalStorage(history: HistoryItem[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

export function saveHistoryItem(item: HistoryItem) {
  localStorage.setItem(ITEM_KEY(item.id), JSON.stringify(item));
  const existing = loadHistoryFromLocalStorage();
  const next = (() => {
    const without = existing.filter((e) => e.id !== item.id);
    return [item, ...without].slice(0, 30); // cap
  })();
  saveHistoryToLocalStorage(next);
}

export function loadHistoryItem(id: string): HistoryItem | null {
  const item = safeJsonParse<HistoryItem>(localStorage.getItem(ITEM_KEY(id)));
  return item ?? null;
}

