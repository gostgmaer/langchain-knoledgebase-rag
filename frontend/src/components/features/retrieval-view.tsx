"use client";

import { ListTree } from "lucide-react";
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
import { useRetrievalLog, useRetrievalLogs } from "@/hooks/use-api";
import { formatDateTime } from "@/lib/utils";

const PAGE_SIZE = 20;

const score = (v: number | null) => (v === null ? "—" : v.toFixed(3));

/** Every retrieval, and for each one why each candidate chunk was or was not used. */
export function RetrievalView() {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useRetrievalLogs(PAGE_SIZE, offset);

  return (
    <div>
      <PageHeader
        title="Retrieval log"
        description="Each retrieval with its candidates, scores and what reached the answer. Queries are stored as a hash, never as text."
      />

      {list.isError ? (
        <QueryError error={list.error} onRetry={() => void list.refetch()} />
      ) : list.isLoading || !list.data ? (
        <Skeleton className="h-40 w-full" />
      ) : list.data.retrievals.length === 0 ? (
        <EmptyState icon={ListTree} title="No retrievals yet" description="Ask a question in Chat and it will appear here." />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Query</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead>Candidates</TableHead>
                <TableHead>Used</TableHead>
                <TableHead>Latency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.data.retrievals.map((r) => (
                <TableRow
                  key={r.retrieval_id}
                  className="cursor-pointer"
                  data-state={selected === r.retrieval_id ? "selected" : undefined}
                  onClick={() => setSelected(selected === r.retrieval_id ? null : r.retrieval_id)}
                >
                  <TableCell className="text-neutral-500">{formatDateTime(r.created_at)}</TableCell>
                  <TableCell>
                    <code className="text-xs">{r.query_hash.slice(0, 10)}</code>
                    <span className="ml-2 text-xs text-neutral-400">{r.query_length} chars</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{r.strategy}</Badge>
                    {r.reranking_enabled && <Badge variant="outline" className="ml-1">rerank</Badge>}
                  </TableCell>
                  <TableCell>{r.candidate_count}</TableCell>
                  <TableCell>{r.selected_count}</TableCell>
                  <TableCell className="text-neutral-500">{r.latency_ms ?? "—"} ms</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="mt-3 flex items-center justify-between text-xs text-neutral-500">
            <span>
              {list.data.offset + 1}–{list.data.offset + list.data.retrievals.length} of {list.data.total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= list.data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      {selected && <RetrievalDetail id={selected} />}
    </div>
  );
}

function RetrievalDetail({ id }: { id: string }) {
  const { role } = useParams<{ role: string }>();
  const { data, isLoading, isError, error, refetch } = useRetrievalLog(id);

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Why these chunks</CardTitle>
      </CardHeader>
      <CardContent>
        {isError ? (
          <QueryError error={error} onRetry={() => void refetch()} />
        ) : isLoading || !data ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <>
            <dl className="mb-4 grid gap-x-6 gap-y-1 text-xs text-neutral-500 sm:grid-cols-2 lg:grid-cols-4">
              <div>Retrieval id: <code>{data.retrieval_id.slice(0, 8)}</code></div>
              <div>Request id: <code>{data.request_id?.slice(0, 8) ?? "—"}</code></div>
              <div>Trace id: <code>{data.trace_id?.slice(0, 8) ?? "—"}</code></div>
              <div>Sub-queries: {data.sub_query_count}</div>
              <div>Search: {data.search_latency_ms ?? "—"} ms</div>
              <div>Rerank: {data.rerank_latency_ms ?? "—"} ms</div>
              <div>Top-k: {data.top_k}</div>
              <div>Min relevance: {data.min_relevance_score ?? "—"}</div>
              <div className="sm:col-span-2 lg:col-span-4">Reranker: {data.reranker_model ?? "—"}</div>
            </dl>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Search #</TableHead>
                  <TableHead>Search score</TableHead>
                  <TableHead>Reranker</TableHead>
                  <TableHead>Final #</TableHead>
                  <TableHead>Used</TableHead>
                  <TableHead>Document</TableHead>
                  <TableHead>Where</TableHead>
                  <TableHead>Chunking</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((res) => (
                  <TableRow key={res.chunk_id} className={res.selected_for_context ? "" : "opacity-60"}>
                    <TableCell>{res.retrieval_rank}</TableCell>
                    <TableCell>{score(res.retrieval_score)}</TableCell>
                    <TableCell>{score(res.reranker_score)}</TableCell>
                    <TableCell>
                      {res.final_rank ?? "—"}
                      {res.reranking_changed_rank && <span className="ml-1 text-xs text-amber-600">moved</span>}
                    </TableCell>
                    <TableCell>
                      {res.selected_for_context ? <Badge variant="success">used</Badge> : <Badge variant="outline">dropped</Badge>}
                    </TableCell>
                    <TableCell>
                      <Link href={`/${role}/documents/${res.document_id}`} className="hover:underline">
                        {res.document_name ?? res.document_id.slice(0, 8)}
                      </Link>
                      {res.document_version !== null && <span className="ml-1 text-xs text-neutral-400">v{res.document_version}</span>}
                      {res.document_is_current === false && <Badge variant="outline" className="ml-1">superseded</Badge>}
                    </TableCell>
                    <TableCell className="text-xs text-neutral-500">
                      chunk {res.chunk_index}
                      {res.page_number !== null && ` · p.${res.page_number}`}
                      {res.section && ` · ${res.section}`}
                    </TableCell>
                    <TableCell className="text-xs text-neutral-500">{res.chunking_strategy ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-3 text-xs text-neutral-400">
              Candidates are ranked by search score first; the reranker then re-scores them and only the best that
              clear the relevance floor become answer context.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
