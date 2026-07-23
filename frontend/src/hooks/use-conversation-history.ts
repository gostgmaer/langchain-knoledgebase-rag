"use client";

import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/lib/session";

export interface ConversationHistoryEntry {
  id: string;
  preview: string;
  updatedAt: string;
}

const MAX_ENTRIES = 30;

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
  const [entries, setEntries] = useState<ConversationHistoryEntry[]>([]);

  const storageKey = session ? `rag-console-conversations-${session.tenantId}-${session.userId}` : null;

  useEffect(() => {
    if (!storageKey) return;
    try {
      const raw = window.localStorage.getItem(storageKey);
      setEntries(raw ? JSON.parse(raw) : []);
    } catch {
      setEntries([]);
    }
  }, [storageKey]);

  const touch = useCallback(
    (id: string, preview: string) => {
      if (!storageKey) return;
      setEntries((prev) => {
        const withoutThis = prev.filter((e) => e.id !== id);
        const existing = prev.find((e) => e.id === id);
        const next = [
          { id, preview: preview || existing?.preview || "New conversation", updatedAt: new Date().toISOString() },
          ...withoutThis,
        ].slice(0, MAX_ENTRIES);
        window.localStorage.setItem(storageKey, JSON.stringify(next));
        return next;
      });
    },
    [storageKey],
  );

  const remove = useCallback(
    (id: string) => {
      if (!storageKey) return;
      setEntries((prev) => {
        const next = prev.filter((e) => e.id !== id);
        window.localStorage.setItem(storageKey, JSON.stringify(next));
        return next;
      });
    },
    [storageKey],
  );

  return { entries, touch, remove };
}
