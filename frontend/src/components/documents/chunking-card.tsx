import { ChunkingBadge } from "@/components/documents/chunking-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DocumentRecord } from "@/lib/api/types";

export function ChunkingCard({ doc }: { doc: DocumentRecord }) {
  const c = doc.chunking;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Chunking</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        <Row label="Method" value={<ChunkingBadge chunking={c} />} />
        {c ? (
          <>
            <Row label="Requested" value={c.requested ?? "—"} />
            <Row label="Applied" value={c.strategy ?? "—"} />
            <Row label="Splitter" value={<code className="text-xs">{c.splitter ?? "—"}</code>} />
            <Row label="Chunk size / overlap" value={`${c.chunk_size ?? "—"} / ${c.chunk_overlap ?? "—"}`} />
            <Row label="Total tokens" value={c.total_tokens ?? "—"} />
          </>
        ) : (
          <p className="text-xs text-neutral-400">
            This document was ingested before the chunking method was recorded. Re-index it to record it.
          </p>
        )}
        <Row label="Chunks" value={doc.chunk_count} />
        <Row label="Extra representations (summary/graph)" value={doc.representation_count} />
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-neutral-100 pb-2 last:border-0 dark:border-neutral-900">
      <span className="text-neutral-500">{label}</span>
      <span>{value}</span>
    </div>
  );
}
