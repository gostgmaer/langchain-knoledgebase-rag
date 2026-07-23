"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useSubmitFeedback } from "@/hooks/use-api";
import type { Message } from "@/lib/api/types";
import { cn } from "@/lib/utils";

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
            "rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap",
            isUser
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900",
            pending && "opacity-70",
          )}
        >
          {message.content || (pending ? "…" : "")}
        </div>
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
