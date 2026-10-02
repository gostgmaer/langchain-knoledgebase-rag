import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DocumentRecord } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

const NOT_RECORDED = <span className="text-neutral-400">not recorded</span>;

/** Where a document came from and which pipeline/models processed it. */
export function ProvenanceCard({ doc }: { doc: DocumentRecord }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Provenance</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        <Row label="Source" value={doc.source_type ?? NOT_RECORDED} />
        <Row label="Uploaded by" value={doc.uploaded_by ? <code className="text-xs">{doc.uploaded_by.slice(0, 8)}</code> : NOT_RECORDED} />
        <Row label="Content hash" value={doc.content_hash ? <code className="text-xs">{doc.content_hash.slice(0, 16)}…</code> : NOT_RECORDED} />
        <Row label="Parser" value={doc.parser_name ?? NOT_RECORDED} />
        <Row
          label="Embedding model"
          value={
            doc.embedding_model
              ? `${doc.embedding_provider ?? ""} ${doc.embedding_model}${doc.embedding_dimensions ? ` (${doc.embedding_dimensions}d)` : ""}`.trim()
              : NOT_RECORDED
          }
        />
        <Row label="Chunking version" value={doc.chunking_version ?? NOT_RECORDED} />
        <Row
          label="Pipeline version"
          value={
            doc.processing_version ? (
              <span className="flex items-center gap-2">
                {doc.processing_version}
                {doc.embedding_is_stale && <Badge variant="outline">outdated — re-index</Badge>}
              </span>
            ) : (
              NOT_RECORDED
            )
          }
        />
        <Row label="Processing stage" value={doc.processing_stage ?? NOT_RECORDED} />
        <Row label="Processed" value={doc.processed_at ? formatDateTime(doc.processed_at) : NOT_RECORDED} />
        {doc.error_reason && <Row label="Error" value={<span className="text-red-600">{doc.error_reason}</span>} />}
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-neutral-100 pb-2 last:border-0 dark:border-neutral-900">
      <span className="text-neutral-500">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}
