"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ChunkingBadge } from "@/components/documents/chunking-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments } from "@/hooks/use-api";

/** The documents in one knowledge base, each with its chunking method and chunk count. */
export function KnowledgeBaseDocuments({ knowledgeBaseId }: { knowledgeBaseId: string }) {
  const { role } = useParams<{ role: string }>();
  const { data, isLoading } = useDocuments(knowledgeBaseId);

  if (isLoading) return <Skeleton className="h-10 w-full" />;
  if (!data || data.documents.length === 0) {
    return <p className="text-xs text-neutral-400">No documents yet.</p>;
  }

  return (
    <ul className="space-y-2 border-t border-neutral-100 pt-3 dark:border-neutral-900">
      {data.documents.map((d) => (
        <li key={d.id} className="flex items-center justify-between gap-2 text-xs">
          <Link href={`/${role}/documents/${d.id}`} className="truncate font-medium hover:underline">
            {d.file_name}
          </Link>
          <span className="flex shrink-0 items-center gap-2 text-neutral-500">
            <ChunkingBadge chunking={d.chunking} />
            {d.chunk_count} chunks
          </span>
        </li>
      ))}
    </ul>
  );
}
