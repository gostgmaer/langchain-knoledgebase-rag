"use client";

import { QueryError } from "@/components/shared/query-error";
import { useRouter } from "next/navigation";

import { ChunkingCard } from "@/components/documents/chunking-card";
import { AccessCard } from "@/components/documents/access-card";
import { ProvenanceCard } from "@/components/documents/provenance-card";
import { SourceCard } from "@/components/documents/source-card";
import { ChunksPanel } from "@/components/documents/chunks-panel";
import { JsonBlock } from "@/components/documents/json-block";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

import { useDocument, useDocumentVersions, useReindexDocument } from "@/hooks/use-api";
import { formatBytes, formatDateTime } from "@/lib/utils";

export function DocumentDetailView({ documentId, basePath }: { documentId: string; basePath: string }) {
  const router = useRouter();
  const { data: doc, isLoading, isError, error, refetch } = useDocument(documentId);
  const { data: versions } = useDocumentVersions(documentId);
  const reindex = useReindexDocument(documentId);

  if (isError) {
    return <QueryError error={error} onRetry={() => void refetch()} />;
  }

  if (isLoading || !doc) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div>
      <PageHeader
        title={doc.file_name}
        description={doc.description ?? undefined}
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              loading={reindex.isPending}
              disabled={!doc.is_current}
              onClick={async () => {
                try {
                  await reindex.mutateAsync();
                  toast.success("Re-index queued. Refresh in a moment to see the new provenance.");
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Could not queue the re-index.");
                }
              }}
            >
              Re-index
            </Button>
            <Button variant="outline" size="sm" onClick={() => router.push(basePath)}>
              Back to documents
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <Row label="Status" value={<StatusBadge status={doc.status} />} />
            <Row label="Version state" value={doc.is_current ? <Badge variant="success">current</Badge> : <Badge variant="outline">superseded</Badge>} />
            <Row label="MIME type" value={doc.mime_type} />
            <Row label="Size" value={formatBytes(doc.size_bytes)} />
            <Row label="File ID" value={<code className="text-xs">{doc.file_id}</code>} />
            <Row label="Uploaded" value={formatDateTime(doc.created_at)} />
            <Row label="Last updated" value={formatDateTime(doc.updated_at)} />
          </CardContent>
        </Card>

        <ChunkingCard doc={doc} />
        <ProvenanceCard doc={doc} />
        {doc.source_id && <SourceCard doc={doc} />}
        <AccessCard doc={doc} />

        <Card>
          <CardHeader>
            <CardTitle>Version history</CardTitle>
          </CardHeader>
          <CardContent>
            {!versions || versions.versions.length === 0 ? (
              <p className="text-sm text-neutral-400">
                No re-uploads yet — versioning only starts once a second upload with the same
                filename but different content arrives.
              </p>
            ) : (
              <ol className="space-y-3">
                {versions.versions.map((v) => (
                  <li key={v.document_id} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">v{v.version_number}</span>
                      {v.document_id === documentId && <Badge variant="secondary">viewing</Badge>}
                      {v.is_current && <Badge variant="success">current</Badge>}
                    </div>
                    <span className="text-xs text-neutral-400">
                      {v.superseded_at ? `superseded ${formatDateTime(v.superseded_at)}` : "active"}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Document metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <JsonBlock value={doc.document_metadata} />
        </CardContent>
      </Card>

      <ChunksPanel documentId={documentId} />
    </div>
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
