"use client";

import { FileText, ScrollText } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

import { useAuditEvents, useObservabilitySummary, useReindexOutdated, useTopDocuments } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";

const RANGES = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
] as const;

const AUDIT_PAGE = 15;

const pct = (v: number | null) => (v === null ? "—" : `${(v * 100).toFixed(1)}%`);
const ms = (v: number | null) => (v === null ? "—" : `${Math.round(v)} ms`);

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <p className="text-xs text-neutral-500">{label}</p>
        <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
        {hint && <p className="mt-1 text-xs text-neutral-400">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export function ObservabilityView() {
  const { role } = useParams<{ role: string }>();
  const [days, setDays] = useState<number>(7);
  const [auditOffset, setAuditOffset] = useState(0);
  const summary = useObservabilitySummary(days);
  const top = useTopDocuments(days);
  const audit = useAuditEvents(AUDIT_PAGE, auditOffset);
  const reindexOutdated = useReindexOutdated();

  const r = summary.data?.retrieval;
  const d = summary.data?.documents;

  return (
    <div>
      <PageHeader
        title="Observability"
        description="How retrieval is performing and how healthy the indexed documents are. These are health signals, not answer accuracy."
        actions={
          <Link href={`/${role}/retrieval`}>
            <Button variant="outline" size="sm">
              Retrieval log
            </Button>
          </Link>
        }
      />

      <Tabs defaultValue={String(days)} className="mb-4">
        <TabsList>
          {RANGES.map((opt) => (
            <TabsTrigger key={opt.value} value={String(opt.value)}>
              <span onClick={() => setDays(opt.value)}>{opt.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {summary.isError ? (
        <QueryError error={summary.error} onRetry={() => void summary.refetch()} />
      ) : summary.isLoading || !r || !d ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Retrievals" value={r.retrievals} />
            <Stat label="Avg / p95 latency" value={`${ms(r.avg_latency_ms)} / ${ms(r.p95_latency_ms)}`} />
            <Stat label="Candidates → kept" value={`${r.avg_candidates ?? "—"} → ${r.avg_selected ?? "—"}`} hint="average per retrieval" />
            <Stat
              label="Citation coverage"
              value={pct(r.citation_coverage)}
              hint={`${r.answers_with_sources} of ${r.answers_total} answers cite a source`}
            />
            <Stat label="Empty retrievals" value={pct(r.empty_rate)} hint="nothing found at all" />
            <Stat label="Low-confidence" value={pct(r.low_confidence_rate)} hint="best reranker score below 0" />
            <Stat label="Stale embeddings" value={d.stale_embeddings} hint={`not on pipeline ${d.current_pipeline_version}`} />
            <Stat label="Never retrieved" value={d.never_retrieved} hint="ready documents no answer has used" />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <Button
              variant="outline"
              size="sm"
              loading={reindexOutdated.isPending}
              disabled={d.stale_embeddings === 0}
              onClick={async () => {
                try {
                  const result = await reindexOutdated.mutateAsync();
                  toast.success(`Re-index queued for ${result.queued} document(s).`);
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Could not queue the re-index.");
                }
              }}
            >
              Re-index {d.stale_embeddings} outdated
            </Button>
            <span className="text-neutral-500">Documents ({d.total}):</span>
            {Object.entries(d.by_status).map(([status, count]) => (
              <Badge key={status} variant={status === "FAILED" ? "destructive" : "secondary"}>
                {status} {count}
              </Badge>
            ))}
          </div>
        </>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Most retrieved documents</CardTitle>
        </CardHeader>
        <CardContent>
          {top.isError ? (
            <QueryError error={top.error} onRetry={() => void top.refetch()} />
          ) : !top.data || top.data.length === 0 ? (
            <EmptyState icon={FileText} title="No retrievals in this period" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Considered</TableHead>
                  <TableHead>Used in answers</TableHead>
                  <TableHead>Avg reranker score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {top.data.map((doc) => (
                  <TableRow key={doc.document_id}>
                    <TableCell>
                      <Link href={`/${role}/documents/${doc.document_id}`} className="font-medium hover:underline">
                        {doc.document_name ?? doc.document_id.slice(0, 8)}
                      </Link>
                    </TableCell>
                    <TableCell>{doc.times_retrieved}</TableCell>
                    <TableCell>{doc.times_selected}</TableCell>
                    <TableCell>{doc.avg_reranker_score ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Audit trail{audit.data ? ` (${audit.data.total})` : ""}</CardTitle>
        </CardHeader>
        <CardContent>
          {audit.isError ? (
            <QueryError error={audit.error} onRetry={() => void audit.refetch()} />
          ) : !audit.data || audit.data.events.length === 0 ? (
            <EmptyState icon={ScrollText} title="No audit events yet" />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Resource</TableHead>
                    <TableHead>Detail</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {audit.data.events.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell className="text-neutral-500">{formatDateTime(e.created_at)}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{e.action}</Badge>
                      </TableCell>
                      <TableCell className="text-neutral-500">{e.resource_type}</TableCell>
                      <TableCell className="max-w-xs truncate text-xs text-neutral-500">
                        {JSON.stringify(e.detail)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-3 flex items-center justify-between text-xs text-neutral-500">
                <span>
                  {audit.data.offset + 1}–{audit.data.offset + audit.data.events.length} of {audit.data.total}
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={auditOffset === 0} onClick={() => setAuditOffset(Math.max(0, auditOffset - AUDIT_PAGE))}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={auditOffset + AUDIT_PAGE >= audit.data.total} onClick={() => setAuditOffset(auditOffset + AUDIT_PAGE)}>
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
