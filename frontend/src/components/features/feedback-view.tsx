"use client";

import { MessagesSquare, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useFeedbackList } from "@/hooks/use-api";
import type { FeedbackRating } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

export function FeedbackView() {
  const [filter, setFilter] = useState<FeedbackRating | "ALL">("ALL");
  const { data, isLoading } = useFeedbackList(filter === "ALL" ? undefined : filter);

  return (
    <div>
      <PageHeader
        title="Feedback"
        description="Thumbs up/down submitted by customers on assistant responses."
      />

      <Tabs defaultValue="ALL" className="mb-4">
        <TabsList>
          {(["ALL", "THUMBS_UP", "THUMBS_DOWN"] as const).map((value) => (
            <TabsTrigger key={value} value={value}>
              <span onClick={() => setFilter(value)}>
                {value === "ALL" ? "All" : value === "THUMBS_UP" ? "Positive" : "Negative"}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.feedback.length === 0 ? (
        <EmptyState icon={MessagesSquare} title="No feedback yet" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rating</TableHead>
              <TableHead>Message</TableHead>
              <TableHead>Comment</TableHead>
              <TableHead>Submitted</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.feedback.map((f) => (
              <TableRow key={f.id}>
                <TableCell>
                  {f.rating === "THUMBS_UP" ? (
                    <Badge variant="success">
                      <ThumbsUp className="mr-1 h-3 w-3" /> Positive
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <ThumbsDown className="mr-1 h-3 w-3" /> Negative
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <code className="text-xs text-neutral-400">{f.message_id.slice(0, 8)}…</code>
                </TableCell>
                <TableCell className="max-w-xs truncate text-neutral-600 dark:text-neutral-400">
                  {f.comment ?? "—"}
                </TableCell>
                <TableCell className="text-neutral-500">{formatDateTime(f.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
