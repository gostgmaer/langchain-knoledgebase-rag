"use client";

import { MessageSquarePlus, X } from "lucide-react";

import type { ConversationHistoryEntry } from "@/hooks/use-conversation-history";
import { cn, formatDateTime, truncate } from "@/lib/utils";

export function HistoryRail({
  entries,
  activeId,
  onSelect,
  onNew,
  onRemove,
}: {
  entries: ConversationHistoryEntry[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="flex w-64 shrink-0 flex-col border-r border-neutral-200 dark:border-neutral-800">
      <button
        onClick={onNew}
        className="m-3 flex items-center justify-center gap-2 rounded-md border border-neutral-200 py-2 text-sm font-medium hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
      >
        <MessageSquarePlus className="h-4 w-4" />
        New chat
      </button>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {entries.length === 0 ? (
          <p className="p-3 text-xs text-neutral-400">
            Past conversations you start will show up here, so you can come back to them later.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {entries.map((entry) => (
              <li key={entry.id} className="group relative">
                <button
                  onClick={() => onSelect(entry.id)}
                  className={cn(
                    "w-full rounded-md px-2.5 py-2 pr-7 text-left text-sm transition-colors",
                    entry.id === activeId
                      ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                      : "hover:bg-neutral-100 dark:hover:bg-neutral-900",
                  )}
                >
                  <div className="truncate font-medium">{truncate(entry.preview, 40)}</div>
                  <div
                    className={cn(
                      "text-xs",
                      entry.id === activeId ? "text-neutral-300 dark:text-neutral-600" : "text-neutral-400",
                    )}
                  >
                    {formatDateTime(entry.updatedAt)}
                  </div>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(entry.id);
                  }}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 opacity-0 hover:bg-black/10 group-hover:opacity-100 dark:hover:bg-white/10"
                  aria-label="Remove from history"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
