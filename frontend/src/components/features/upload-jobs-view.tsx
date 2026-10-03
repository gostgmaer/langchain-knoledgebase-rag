"use client";

import { Search, UploadCloud } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useUploadJob, useUploadJobs } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";

export function UploadJobsView() {
  const { data, isLoading, isError, error, refetch } = useUploadJobs();

  const [draft, setDraft] = useState("");
  const [lookupId, setLookupId] = useState<string | null>(null);
  const { data: lookedUpJob, isFetching: lookupFetching, isError: lookupFailed } = useUploadJob(lookupId, true);

  return (
    <div>
      <PageHeader
        title="Upload Jobs"
        description="Real-time pipeline progress (queued → running → succeeded/failed) for every document upload."
      />

      <form
        className="mb-6 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setLookupId(draft.trim() || null);
        }}
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Jump to a specific upload_job_id (UUID)…"
          className="font-mono"
        />
        <Button type="submit" variant="outline" loading={lookupFetching}>
          <Search className="h-4 w-4" />
          Look up
        </Button>
      </form>

      {lookupId && (lookedUpJob || lookupFailed) && (
        <Card className="mb-6">
          <CardContent className="pt-5 text-sm">
            {lookupFailed ? (
              <p className="text-red-600">No upload job found with that ID.</p>
            ) : (
              lookedUpJob && (
                <div className="grid gap-2">
                  <Row label="File" value={lookedUpJob.file_name} />
                  <Row label="Status" value={<StatusBadge status={lookedUpJob.status} />} />
                  <Row label="Document ID" value={lookedUpJob.document_id ?? "—"} />
                  <Row label="Error" value={lookedUpJob.error ?? "—"} />
                  <Row label="Started" value={formatDateTime(lookedUpJob.started_at)} />
                  <Row label="Finished" value={formatDateTime(lookedUpJob.finished_at)} />
                </div>
              )
            )}
          </CardContent>
        </Card>
      )}

      {isError ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.upload_jobs.length === 0 ? (
        <EmptyState icon={UploadCloud} title="No upload jobs yet" description="Upload a document to see its pipeline progress here." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Error</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Finished</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.upload_jobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell className="max-w-xs truncate font-medium">{job.file_name}</TableCell>
                <TableCell>
                  <StatusBadge status={job.status} />
                </TableCell>
                <TableCell className="max-w-xs truncate text-neutral-600 dark:text-neutral-400">
                  {job.error ?? "—"}
                </TableCell>
                <TableCell className="text-neutral-500">{formatDateTime(job.started_at)}</TableCell>
                <TableCell className="text-neutral-500">{formatDateTime(job.finished_at)}</TableCell>
                <TableCell className="text-neutral-500">{formatDateTime(job.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
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
