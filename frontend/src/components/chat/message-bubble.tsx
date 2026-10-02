"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useSubmitFeedback } from "@/hooks/use-api";
import type { Message } from "@/lib/api/types";
import { cn } from "@/lib/utils";

// Minimal, compact element styling to match this bubble's existing text-sm/neutral
// aesthetic — deliberately not the @tailwindcss/typography plugin's `prose` classes,
// which are sized/spaced for full articles and would need as much override work to
// look native here as writing this directly does.
const MARKDOWN_COMPONENTS: Components = {
  p: ({ children }) => <p className="[&:not(:first-child)]:mt-2">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mt-2 list-disc space-y-1 pl-5 first:mt-0">{children}</ul>,
  ol: ({ children }) => <ol className="mt-2 list-decimal space-y-1 pl-5 first:mt-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="underline underline-offset-2"
    >
      {children}
    </a>
  ),
  h1: ({ children }) => <h1 className="mt-2 text-base font-semibold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-2 text-[0.95rem] font-semibold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-2 text-sm font-semibold first:mt-0">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="mt-2 border-l-2 border-neutral-300 pl-3 text-neutral-600 first:mt-0 dark:border-neutral-700 dark:text-neutral-400">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const isBlock = /language-/.test(className ?? "");
    return isBlock ? (
      <code className={cn("block", className)}>{children}</code>
    ) : (
      <code className="rounded bg-black/[0.06] px-1 py-0.5 font-mono text-[0.85em] dark:bg-white/10">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mt-2 overflow-x-auto rounded-md bg-black/[0.06] p-3 font-mono text-xs first:mt-0 dark:bg-white/10">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="mt-2 overflow-x-auto first:mt-0">
      <table className="border-collapse text-left text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-neutral-200 px-2 py-1 font-semibold dark:border-neutral-700">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-neutral-200 px-2 py-1 dark:border-neutral-700">{children}</td>
  ),
  hr: () => <hr className="my-2 border-neutral-200 dark:border-neutral-700" />,
};

export function MessageBubble({ message, pending }: { message: Message; pending?: boolean }) {
  const isUser = message.role === "USER";
  const submitFeedback = useSubmitFeedback();
  const [rated, setRated] = useState<"THUMBS_UP" | "THUMBS_DOWN" | null>(null);

  async function rate(rating: "THUMBS_UP" | "THUMBS_DOWN") {
    try {
      await submitFeedback.mutateAsync({ message_id: message.id, rating });
      setRated(rating);
      toast.success(rating === "THUMBS_UP" ? "Thanks for the feedback!" : "Feedback recorded.");
    } catch {
      toast.error("Could not record feedback.");
    }
  }

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[75%] flex-col gap-1", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-lg px-4 py-2.5 text-sm",
            isUser
              ? "bg-neutral-900 text-white whitespace-pre-wrap dark:bg-neutral-100 dark:text-neutral-900"
              : "border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900",
            pending && "opacity-70",
          )}
        >
          {isUser || !message.content ? (
            message.content || (pending ? "…" : "")
          ) : (
            // Only assistant responses render as markdown — a user's own message shows
            // exactly what they typed (the common chat-UI convention), and the assistant
            // is the only side that ever produces formatted content worth parsing.
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
              {message.content}
            </ReactMarkdown>
          )}
        </div>
        {message.sources && message.sources.length > 0 && (
          <ul className="flex flex-col gap-0.5 text-xs text-neutral-500" aria-label="Sources">
            {message.sources.map((s) => (
              <li key={s.label}>
                <span className="font-medium">{s.label}</span>{" "}
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noreferrer noopener" className="underline underline-offset-2">
                    {s.document_name ?? s.url}
                  </a>
                ) : (
                  (s.document_name ?? "Unknown document")
                )}
                {s.source_type && s.source_type !== "upload" && ` · ${s.source_name ?? s.source_type}`}
                {s.page_number !== null && ` · page ${s.page_number}`}
                {s.section && ` · ${s.section}`}
                {s.updated_at && ` · updated ${new Date(s.updated_at).toLocaleDateString()}`}
              </li>
            ))}
          </ul>
        )}
        {message.role === "ASSISTANT" && !pending && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className={cn("h-6 w-6", rated === "THUMBS_UP" && "text-emerald-600")}
              onClick={() => rate("THUMBS_UP")}
              aria-label="Good response"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn("h-6 w-6", rated === "THUMBS_DOWN" && "text-red-600")}
              onClick={() => rate("THUMBS_DOWN")}
              aria-label="Bad response"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
