"use client";

import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocument, useDocumentVersions } from "@/hooks/use-api";
import { formatBytes, formatDateTime } from "@/lib/utils";

export function DocumentDetailView({ documentId, basePath }: { documentId: string; basePath: string }) {
  const router = useRouter();
  const { data: doc, isLoading } = useDocument(documentId);
  const { data: versions } = useDocumentVersions(documentId);

  if (isLoading || !doc) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div>
      <PageHeader
        title={doc.file_name}
        description={doc.description ?? undefined}
        actions={
          <Button variant="outline" size="sm" onClick={() => router.push(basePath)}>
            Back to documents
          </Button>
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
