"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

import { useSession } from "@/lib/session";

export interface ConversationHistoryEntry {
  id: string;
  preview: string;
  updatedAt: string;
}

const MAX_ENTRIES = 30;

// localStorage is an external store: subscribe to it instead of copying it into state
// from an effect. The "storage" event covers other tabs; our own writes notify directly.
const listeners = new Set<() => void>();

function subscribe(callback: () => void) {
  listeners.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", callback);
  };
}

function readRaw(key: string | null): string | null {
  if (!key) return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, entries: ConversationHistoryEntry[]) {
  try {
    window.localStorage.setItem(key, JSON.stringify(entries));
  } catch {
    // Storage unavailable (private browsing, quota): history just won't persist.
  }
  listeners.forEach((notify) => notify());
}

function parse(raw: string | null): ConversationHistoryEntry[] {
  if (!raw) return [];
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

/**
 * The backend has no "list my conversations" endpoint — every
 * conversation route is fetch-by-id only (see docs/BUILD_STATUS.md's
 * Session Management notes). This is a real, disclosed limitation,
 * not a frontend gap: without it, a customer would have no way to
 * ever resume a past chat, so this keeps a local index of
 * conversation ids this browser has actually started, per identity,
 * good enough to resume from the same device/browser.
 */
export function useConversationHistory() {
  const { session } = useSession();

  const storageKey = session ? `rag-console-conversations-${session.tenantId}-${session.userId}` : null;

  const raw = useSyncExternalStore(
    subscribe,
    () => readRaw(storageKey),
    () => null,
  );
  const entries = useMemo(() => parse(raw), [raw]);

  const touch = useCallback(
    (id: string, preview: string) => {
      if (!storageKey) return;
      const current = parse(readRaw(storageKey));
      const existing = current.find((e) => e.id === id);
      const next = [
        { id, preview: preview || existing?.preview || "New conversation", updatedAt: new Date().toISOString() },
        ...current.filter((e) => e.id !== id),
      ].slice(0, MAX_ENTRIES);
      write(storageKey, next);
    },
    [storageKey],
  );

  const remove = useCallback(
    (id: string) => {
      if (!storageKey) return;
      write(
        storageKey,
        parse(readRaw(storageKey)).filter((e) => e.id !== id),
      );
    },
    [storageKey],
  );

  return { entries, touch, remove };
}
