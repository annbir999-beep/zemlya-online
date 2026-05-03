"use client";

const KEY = "compare_ids";
const MAX = 5;

type Listener = (ids: number[]) => void;
const listeners = new Set<Listener>();

function read(): number[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x) => typeof x === "number" && Number.isFinite(x)).slice(0, MAX);
  } catch {
    return [];
  }
}

function write(ids: number[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(ids.slice(0, MAX)));
  listeners.forEach((l) => l(ids));
  // Sync across tabs
  window.dispatchEvent(new Event("compare-changed"));
}

export const compare = {
  get: read,
  has: (id: number) => read().includes(id),
  add: (id: number): { ok: boolean; reason?: string } => {
    const ids = read();
    if (ids.includes(id)) return { ok: false, reason: "already" };
    if (ids.length >= MAX) return { ok: false, reason: "limit" };
    write([...ids, id]);
    return { ok: true };
  },
  remove: (id: number) => write(read().filter((x) => x !== id)),
  clear: () => write([]),
  toggle: (id: number) => {
    const ids = read();
    if (ids.includes(id)) {
      write(ids.filter((x) => x !== id));
      return false;
    }
    if (ids.length < MAX) {
      write([...ids, id]);
      return true;
    }
    return null; // over limit
  },
  url: () => {
    const ids = read();
    return ids.length ? `/compare?ids=${ids.join(",")}` : "/compare";
  },
  subscribe: (listener: Listener) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  MAX,
};
