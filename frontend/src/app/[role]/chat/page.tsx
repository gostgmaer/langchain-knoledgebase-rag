"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { HistoryRail } from "@/components/chat/history-rail";
import { MessageBubble } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useConversationHistory } from "@/hooks/use-conversation-history";
import { useConversationMessages } from "@/hooks/use-api";
import { ApiError, streamChat } from "@/lib/api/client";
import { conversations } from "@/lib/api/resources";
import type { ChatFilters, Message } from "@/lib/api/types";
import { useSession } from "@/lib/session";

function chatFilters(type: string, category: string, tags: string): { filters?: ChatFilters } {
  const list = (value: string) => value.split(",").map((s) => s.trim()).filter(Boolean);
  const filters: ChatFilters = {
    ...(list(type).length && { document_types: list(type) }),
    ...(list(category).length && { categories: list(category) }),
    ...(list(tags).length && { tags: list(tags) }),
  };
  return Object.keys(filters).length ? { filters } : {};
}

function newId(): string {
  return crypto.randomUUID();
}

export default function ChatPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const { entries, touch, remove } = useConversationHistory();
  const [conversationId, setConversationId] = useState<string>(() => newId());
  const [draft, setDraft] = useState("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [pendingAssistant, setPendingAssistant] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [filterType, setFilterType] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data } = useConversationMessages(conversationId);
  const messages: Message[] = useMemo(() => data?.messages ?? [], [data]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingUser, pendingAssistant]);

  async function handleSend() {
    const text = draft.trim();
    if (!text || !session || sending) return;

    setDraft("");
    setSending(true);
    // Rendered immediately below, before the request even starts — the
    // real message only exists in `messages` once the server-fetched
    // history refetches in the `finally` block below, which previously
    // meant the user's own message stayed invisible for the entire
    // duration of the assistant's reply.
    setPendingUser(text);
    setPendingAssistant("");
    touch(conversationId, text);

    try {
      await streamChat(
        {
          message: text,
          conversation_id: conversationId,
          ...chatFilters(filterType, filterCategory, filterTags),
        },
        { tenantId: session.tenantId, userId: session.userId },
        (event) => {
          if (event.type === "token" && typeof event.content === "string") {
            setPendingAssistant((prev) => (prev ?? "") + event.content);
          }
          if (event.type === "error") {
            toast.error(typeof event.message === "string" ? event.message : "The answer could not be completed.");
          }
        },
      );
    } catch (err) {
      // ApiError carries the server's own message (for example "not a member of any workspace",
      // or the provider-unavailable text); only fall back to the generic hint for network failures.
      toast.error(err instanceof ApiError ? err.message : "Chat request failed — is the backend running?");
    } finally {
      setSending(false);
      // Explicit fetch + setQueryData rather than invalidateQueries/
      // refetchQueries: both only refetch queries React Query
      // considers "active" at the exact moment they're called, which
      // this one intermittently wasn't, leaving the just-sent
      // exchange invisible until the next full remount. A direct
      // fetch has no such condition to race.
      if (session) {
        try {
          const fresh = await conversations.messages(
            { tenantId: session.tenantId, userId: session.userId },
            conversationId,
          );
          queryClient.setQueryData(["conversation-messages", session.tenantId, conversationId], fresh);
        } catch {
          // Best-effort refresh — the next natural fetch will catch up.
        }
      }
      setPendingUser(null);
      setPendingAssistant(null);
    }
  }

  function handleSelectConversation(id: string) {
    setConversationId(id);
    setPendingUser(null);
    setPendingAssistant(null);
  }

  function handleNewChat() {
    setConversationId(newId());
    setPendingUser(null);
    setPendingAssistant(null);
  }

  return (
    <div className="flex h-full">
      <HistoryRail
        entries={entries}
        activeId={conversationId}
        onSelect={handleSelectConversation}
        onNew={handleNewChat}
        onRemove={remove}
      />

      <div className="flex flex-1 flex-col pl-6">
        <div className="mb-3">
          <h1 className="text-xl font-semibold tracking-tight">Chat</h1>
          <p className="text-sm text-neutral-500">Conversation {conversationId.slice(0, 8)}…</p>
        </div>

        <div className="flex flex-1 flex-col gap-3 overflow-y-auto rounded-lg border border-neutral-200 bg-neutral-50/50 p-4 dark:border-neutral-800 dark:bg-neutral-900/30">
          {messages.length === 0 && pendingUser === null && pendingAssistant === null && (
            <p className="m-auto text-sm text-neutral-400">Say something to get started.</p>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {pendingUser !== null && (
            <MessageBubble
              message={{
                id: "pending-user",
                conversation_id: conversationId,
                role: "USER",
                content: pendingUser,
                created_at: new Date().toISOString(),
              }}
            />
          )}
          {pendingAssistant !== null && (
            <MessageBubble
              message={{
                id: "pending",
                conversation_id: conversationId,
                role: "ASSISTANT",
                content: pendingAssistant,
                created_at: new Date().toISOString(),
              }}
              pending
            />
          )}
          <div ref={scrollRef} />
        </div>

        <details className="mt-3 text-xs text-neutral-500">
          <summary className="cursor-pointer select-none">
            Limit answers to documents…
            {(filterType || filterCategory || filterTags) && <span className="ml-1 text-neutral-900 dark:text-neutral-100">(filters on)</span>}
          </summary>
          <div className="mt-2 flex flex-wrap gap-2">
            <Input className="h-8 w-36 text-xs" placeholder="type, e.g. policy" value={filterType} onChange={(e) => setFilterType(e.target.value)} aria-label="Document type filter" />
            <Input className="h-8 w-36 text-xs" placeholder="category, e.g. hr" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} aria-label="Category filter" />
            <Input className="h-8 w-40 text-xs" placeholder="tags (all required)" value={filterTags} onChange={(e) => setFilterTags(e.target.value)} aria-label="Tags filter" />
          </div>
        </details>

        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask anything… (Enter to send, Shift+Enter for a new line)"
            className="min-h-12"
          />
          <Button type="submit" loading={sending} disabled={!draft.trim()}>
            <Send className="h-4 w-4" />
            Send
          </Button>
        </form>
      </div>
    </div>
  );
}
