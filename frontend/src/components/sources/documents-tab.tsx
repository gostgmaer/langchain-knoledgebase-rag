"use client";

import { FileText } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { QueryError } from "@/components/shared/query-error";
import { freshnessLabel, relativeTime } from "@/components/sources/common";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSourceAction, useSourceDocuments } from "@/hooks/use-api";
import type { ExternalDocument } from "@/lib/api/types";

const PAGE = 25;
const VARIANT: Record<ExternalDocument["status"], BadgeProps["variant"]> = {
  indexed: "success",
  updated: "success",
  discovered: "outline",
  pending: "warning",
  fetching: "warning",
  processing: "warning",
  deleted: "outline",
  failed: "destructive",
};

export function DocumentsTab({ sourceId }: { sourceId: string }) {
  const { role } = useParams<{ role: string }>();
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const docs = useSourceDocuments(sourceId, PAGE, offset, status, q);
  const action = useSourceAction(sourceId);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input className="h-8 w-56 text-xs" placeholder="Search titles" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} aria-label="Search titles" />
        <Select className="h-8 w-40 text-xs" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} aria-label="Filter by status">
          <option value="">All statuses</option>
          {["indexed", "updated", "failed", "deleted"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>

      {docs.isError ? (
        <QueryError error={docs.error} onRetry={() => void docs.refetch()} />
      ) : docs.isLoading || !docs.data ? (
        <Skeleton className="h-40 w-full" />
      ) : docs.data.documents.length === 0 ? (
        <EmptyState icon={FileText} title="No documents" description="Run a sync to index this source." />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Source version</TableHead>
                <TableHead>Changed at source</TableHead>
                <TableHead>Indexed</TableHead>
                <TableHead>Freshness</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {docs.data.documents.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="max-w-sm">
                    {d.document_id ? (
                      <Link href={`/${role}/documents/${d.document_id}`} className="font-medium hover:underline">
                        {d.title ?? d.external_id}
                      </Link>
                    ) : (
                      <span className="font-medium">{d.title ?? d.external_id}</span>
                    )}
                    {d.canonical_url && (
                      <a href={d.canonical_url} target="_blank" rel="noreferrer noopener" className="block truncate text-xs text-neutral-500 hover:underline">
                        {d.canonical_url}
                      </a>
                    )}
                    {d.last_error && <p className="text-xs text-red-600">{d.last_error}</p>}
                  </TableCell>
                  <TableCell><Badge variant={VARIANT[d.status]}>{d.status}</Badge></TableCell>
                  <TableCell className="text-xs text-neutral-500">{d.external_version ?? "—"}</TableCell>
                  <TableCell className="text-neutral-500">{d.external_updated_at ? relativeTime(d.external_updated_at) : "—"}</TableCell>
                  <TableCell className="text-neutral-500">{d.last_indexed_at ? relativeTime(d.last_indexed_at) : "—"}</TableCell>
                  <TableCell className="text-neutral-500">{freshnessLabel(d.freshness_seconds)}</TableCell>
                  <TableCell className="text-right">
                    {d.status === "failed" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            await action.retryDocument.mutateAsync(d.id);
                            toast.success("It will be retried on the next sync.");
                          } catch (err) {
                            toast.error(err instanceof Error ? err.message : "Could not queue the retry.");
                          }
                        }}
                      >
                        Retry
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between text-xs text-neutral-500">
            <span>{docs.data.offset + 1}–{docs.data.offset + docs.data.documents.length} of {docs.data.total}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE >= docs.data.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
