"use client";

import { Fragment, useState } from "react";

import { JsonBlock } from "@/components/documents/json-block";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDocumentChunks } from "@/hooks/use-api";

const PAGE_SIZE = 25;

/** Every stored chunk of a document with its full text and all metadata (click a row to expand). */
export function ChunksPanel({ documentId }: { documentId: string }) {
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const { data, isLoading, isError, error, refetch } = useDocumentChunks(documentId, PAGE_SIZE, offset);

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>Chunks{data ? ` (${data.total})` : ""}</CardTitle>
      </CardHeader>
      <CardContent>
        {isError ? (
          <QueryError error={error} onRetry={() => void refetch()} />
        ) : isLoading || !data ? (
          <Skeleton className="h-40 w-full" />
        ) : data.chunks.length === 0 ? (
          <p className="text-sm text-neutral-400">No chunks stored for this document.</p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Page</TableHead>
                  <TableHead>Section</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Chars</TableHead>
                  <TableHead>Preview</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.chunks.map((c) => (
                  <Fragment key={c.id}>
                    <TableRow className="cursor-pointer" onClick={() => setOpen(open === c.id ? null : c.id)}>
                      <TableCell>{c.chunk_index}</TableCell>
                      <TableCell>
                        <Badge variant={c.kind === "chunk" ? "secondary" : "outline"}>{c.kind}</Badge>
                      </TableCell>
                      <TableCell>{c.page_number ?? "—"}</TableCell>
                      <TableCell>{c.section ?? "—"}</TableCell>
                      <TableCell>{c.token_count}</TableCell>
                      <TableCell>{c.character_count}</TableCell>
                      <TableCell className="max-w-xs truncate text-neutral-500">{c.content}</TableCell>
                    </TableRow>
                    {open === c.id && (
                      <TableRow>
                        <TableCell colSpan={7}>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div>
                              <p className="mb-1 text-xs font-medium text-neutral-500">Content</p>
                              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-neutral-100 p-3 text-xs dark:bg-neutral-900">
                                {c.content}
                              </pre>
                            </div>
                            <div>
                              <p className="mb-1 text-xs font-medium text-neutral-500">Metadata</p>
                              <JsonBlock
                                value={{
                                  ...c.metadata,
                                  content_hash: c.content_hash,
                                  chunking_strategy: c.chunking_strategy ?? c.metadata.chunking_strategy,
                                  chunking_version: c.chunking_version,
                                  embedding_provider: c.embedding_provider,
                                  embedding_model: c.embedding_model,
                                  embedding_dimensions: c.embedding_dimensions,
                                  pipeline_version: c.pipeline_version,
                                  indexed_at: c.indexed_at,
                                  ...(c.start_offset !== null && { start_offset: c.start_offset }),
                                  ...(c.end_offset !== null && { end_offset: c.end_offset }),
                                }}
                              />
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
            <div className="mt-3 flex items-center justify-between text-xs text-neutral-500">
              <span>
                {data.offset + 1}–{data.offset + data.chunks.length} of {data.total}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                  Previous
                </Button>
                <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
