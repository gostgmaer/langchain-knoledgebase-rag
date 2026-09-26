"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { freshnessLabel, relativeTime } from "@/components/sources/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DocumentRecord } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

const NOT_RECORDED = <span className="text-neutral-400">—</span>;

/** Where a document from a connected source came from, its version there, and how fresh our copy is. */
export function SourceCard({ doc }: { doc: DocumentRecord }) {
  const { role } = useParams<{ role: string }>();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Source</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        <Row label="Knowledge source" value={doc.source_id ? <Link className="underline" href={`/${role}/knowledge-sources/${doc.source_id}`}>{doc.source_name ?? doc.source_type}</Link> : NOT_RECORDED} />
        <Row label="Type" value={doc.source_type ?? NOT_RECORDED} />
        <Row label="External id" value={doc.external_id ? <code className="break-all text-xs">{doc.external_id}</code> : NOT_RECORDED} />
        <Row
          label="Original"
          value={doc.canonical_url ? <a className="break-all underline" href={doc.canonical_url} target="_blank" rel="noreferrer noopener">{doc.canonical_url}</a> : NOT_RECORDED}
        />
        <Row label="Source version" value={doc.external_version ?? NOT_RECORDED} />
        <Row label="Changed at source" value={doc.external_updated_at ? `${formatDateTime(doc.external_updated_at)} (${relativeTime(doc.external_updated_at)})` : NOT_RECORDED} />
        <Row label="Last synced" value={doc.last_synced_at ? relativeTime(doc.last_synced_at) : NOT_RECORDED} />
        <Row label="Sync id" value={doc.sync_id ? <code className="text-xs">{doc.sync_id.slice(0, 8)}</code> : NOT_RECORDED} />
        <Row label="Freshness" value={doc.freshness_seconds !== null ? `indexed ${freshnessLabel(doc.freshness_seconds)} after the source changed` : NOT_RECORDED} />
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-neutral-100 pb-2 last:border-0 dark:border-neutral-900">
      <span className="text-neutral-500">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}
