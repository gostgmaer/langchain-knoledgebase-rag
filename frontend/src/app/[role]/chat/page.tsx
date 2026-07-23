"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { HistoryRail } from "@/components/chat/history-rail";
import { MessageBubble } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useConversationHistory } from "@/hooks/use-conversation-history";
import { useConversationMessages } from "@/hooks/use-api";
import { streamChat } from "@/lib/api/client";
import type { Message } from "@/lib/api/types";
import { useSession } from "@/lib/session";

function newId(): string {
  return crypto.randomUUID();
}

export default function ChatPage() {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const { entries, touch, remove } = useConversationHistory();
  const [conversationId, setConversationId] = useState<string>(() => newId());
  const [draft, setDraft] = useState("");
  const [pendingAssistant, setPendingAssistant] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data } = useConversationMessages(conversationId);
  const messages: Message[] = data?.messages ?? [];

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingAssistant]);

  async function handleSend() {
    const text = draft.trim();
    if (!text || !session || sending) return;

    setDraft("");
    setSending(true);
    setPendingAssistant("");
    touch(conversationId, text);

    try {
      await streamChat(
        { message: text, conversation_id: conversationId },
        { tenantId: session.tenantId, userId: session.userId },
        (event) => {
          if (event.type === "token" && typeof event.content === "string") {
            setPendingAssistant((prev) => (prev ?? "") + event.content);
          }
        },
      );
    } catch {
      toast.error("Chat request failed — is the backend running?");
    } finally {
      setPendingAssistant(null);
      setSending(false);
      await queryClient.invalidateQueries({
        queryKey: ["conversation-messages", session?.tenantId, conversationId],
      });
    }
  }

  function handleSelectConversation(id: string) {
    setConversationId(id);
    setPendingAssistant(null);
  }

  function handleNewChat() {
    setConversationId(newId());
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
          {messages.length === 0 && pendingAssistant === null && (
            <p className="m-auto text-sm text-neutral-400">Say something to get started.</p>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
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
