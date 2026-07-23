"use client";

import { FileText, History, Trash2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { UploadDropzone } from "@/components/documents/upload-dropzone";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDeleteDocument, useDocuments } from "@/hooks/use-api";
import { formatBytes, formatDateTime } from "@/lib/utils";

export function DocumentsView({ basePath }: { basePath: string }) {
  const { data, isLoading } = useDocuments();
  const deleteDocument = useDeleteDocument();

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Upload documents for ingestion — loaded, cleaned, chunked, embedded, and indexed in the background."
      />

      <div className="mb-6">
        <UploadDropzone />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : !data || data.documents.length === 0 ? (
        <EmptyState icon={FileText} title="No documents yet" description="Upload one above to get started." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Uploaded</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.documents.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell>
                  <Link href={`${basePath}/${doc.id}`} className="font-medium hover:underline">
                    {doc.file_name}
                  </Link>
                </TableCell>
                <TableCell>
                  <StatusBadge status={doc.status} />
                </TableCell>
                <TableCell>
                  {doc.is_current ? (
                    <Badge variant="success">current</Badge>
                  ) : (
                    <Badge variant="outline">superseded</Badge>
                  )}
                </TableCell>
                <TableCell className="text-neutral-500">{formatBytes(doc.size_bytes)}</TableCell>
                <TableCell className="text-neutral-500">{formatDateTime(doc.created_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Link href={`${basePath}/${doc.id}`}>
                      <Button variant="ghost" size="icon" aria-label="Version history">
                        <History className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete"
                      onClick={async () => {
                        if (!confirm(`Delete "${doc.file_name}"? This removes it from the search index.`)) return;
                        try {
                          await deleteDocument.mutateAsync(doc.id);
                          toast.success("Document deleted.");
                        } catch {
                          toast.error("Could not delete document.");
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
