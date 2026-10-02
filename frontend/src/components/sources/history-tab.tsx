"use client";

import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { QueryError } from "@/components/shared/query-error";
import { RunStatusBadge, duration } from "@/components/sources/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSourceRun, useSourceRuns } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";
import { History } from "lucide-react";

const PAGE = 15;

export function HistoryTab({ sourceId }: { sourceId: string }) {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const runs = useSourceRuns(sourceId, PAGE, offset);

  if (runs.isError) return <QueryError error={runs.error} onRetry={() => void runs.refetch()} />;
  if (runs.isLoading || !runs.data) return <Skeleton className="h-40 w-full" />;
  if (runs.data.runs.length === 0) return <EmptyState icon={History} title="No syncs yet" description="Start one from Overview." />;

  return (
    <div className="grid gap-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Started</TableHead>
            <TableHead>Trigger</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Discovered</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead>Removed</TableHead>
            <TableHead>Unchanged</TableHead>
            <TableHead>Failed</TableHead>
            <TableHead>Duration</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.data.runs.map((r) => (
            <TableRow key={r.id} className="cursor-pointer" onClick={() => setSelected(selected === r.id ? null : r.id)}>
              <TableCell className="text-neutral-500">{formatDateTime(r.started_at ?? r.completed_at)}</TableCell>
              <TableCell>{r.trigger}</TableCell>
              <TableCell><RunStatusBadge status={r.status} /></TableCell>
              <TableCell>{r.documents_discovered}</TableCell>
              <TableCell>{r.documents_created}</TableCell>
              <TableCell>{r.documents_updated}</TableCell>
              <TableCell>{r.documents_deleted}</TableCell>
              <TableCell>{r.documents_skipped}</TableCell>
              <TableCell className={r.documents_failed ? "text-red-600" : ""}>{r.documents_failed}</TableCell>
              <TableCell className="text-neutral-500">{duration(r.duration_seconds)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center justify-between text-xs text-neutral-500">
        <span>{runs.data.offset + 1}–{runs.data.offset + runs.data.runs.length} of {runs.data.total}</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
          <Button variant="outline" size="sm" disabled={offset + PAGE >= runs.data.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
        </div>
      </div>
      {selected && <RunDetail sourceId={sourceId} runId={selected} />}
    </div>
  );
}

function RunDetail({ sourceId, runId }: { sourceId: string; runId: string }) {
  const run = useSourceRun(sourceId, runId);
  if (run.isError) return <QueryError error={run.error} onRetry={() => void run.refetch()} />;
  if (!run.data) return <Skeleton className="h-24 w-full" />;
  const r = run.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sync {r.id.slice(0, 8)}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <dl className="grid gap-x-6 gap-y-1 text-xs text-neutral-500 sm:grid-cols-2 lg:grid-cols-4">
          <div>Sync id: <code>{r.id}</code></div>
          <div>Trace id: <code>{r.trace_id?.slice(0, 8) ?? "—"}</code></div>
          <div>Request id: <code>{r.request_id?.slice(0, 8) ?? "—"}</code></div>
          <div>Permissions updated: {r.permissions_updated}</div>
          {typeof r.stats.requests === "number" && <div>API requests: {r.stats.requests as number}</div>}
          {typeof r.stats.renamed === "number" && <div>Renamed/moved: {r.stats.renamed as number}</div>}
          {typeof r.stats.quarantined === "number" && r.stats.quarantined > 0 && <div>Quarantined: {r.stats.quarantined as number}</div>}
          {typeof r.stats.unmapped_principals === "number" && r.stats.unmapped_principals > 0 && <div>Unmapped principals: {r.stats.unmapped_principals as number}</div>}
        </dl>
        {r.error_summary && <p className="text-red-600">{r.error_summary}</p>}
        {r.errors.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Document</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {r.errors.map((e, i) => (
                <TableRow key={`${e.external_id}-${i}`}>
                  <TableCell className="max-w-xs truncate">{e.title || e.external_id}</TableCell>
                  <TableCell>{e.stage}</TableCell>
                  <TableCell className="text-xs text-red-600">{e.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-xs text-neutral-500">No document errors.</p>
        )}
      </CardContent>
    </Card>
  );
}
