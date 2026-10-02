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

  // This card is "what's actually in this knowledge base right now" — a superseded
  // version or an archived (deleted-but-retained) document isn't part of that, even
  // though the documents.list() endpoint returns full history for the real Documents
  // page. Filtered here, not at the API layer, so that page's own history view is
  // unaffected.
  const current = data.documents.filter((d) => d.is_current && d.status !== "ARCHIVED");
  const archivedCount = data.documents.length - current.length;

  if (current.length === 0) {
    return <p className="text-xs text-neutral-400">No documents yet.</p>;
  }

  return (
    <div className="space-y-2 border-t border-neutral-100 pt-3 dark:border-neutral-900">
      <ul className="space-y-2">
        {current.map((d) => (
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
      {archivedCount > 0 && (
        <p className="text-xs text-neutral-400">
          +{archivedCount} archived/superseded — see{" "}
          <Link href={`/${role}/documents`} className="underline">
            Documents
          </Link>{" "}
          for full history.
        </p>
      )}
    </div>
  );
}
