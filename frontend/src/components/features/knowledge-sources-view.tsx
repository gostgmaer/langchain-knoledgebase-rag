"use client";

import { Database, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { RunStatusBadge, SourceIcon, SourceStatusBadge, intervalLabel, relativeTime } from "@/components/sources/common";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useKnowledgeSources, useSourceAction, useSourceTypes, useSourcesSummary } from "@/hooks/use-api";
import type { KnowledgeSource } from "@/lib/api/types";

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

function Summary() {
  const { data } = useSourcesSummary();
  if (!data) return <Skeleton className="mb-6 h-24 w-full" />;
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Sources" value={data.total_sources} hint={`${data.connected_sources} connected · ${data.paused_sources} paused`} />
      <Stat label="Needing attention" value={data.sources_with_errors + data.disconnected_sources} hint={`${data.sources_with_errors} errors · ${data.disconnected_sources} disconnected`} />
      <Stat label="Documents / chunks" value={`${data.total_documents} / ${data.total_chunks}`} hint={`${data.failed_documents} failed · ${data.stale_documents} behind the source`} />
      <Stat
        label="Today"
        value={`+${data.documents_added_today} ~${data.documents_updated_today} −${data.documents_deleted_today}`}
        hint={data.last_sync_duration_seconds !== null ? `last sync took ${data.last_sync_duration_seconds}s` : "no syncs yet"}
      />
    </div>
  );
}

function SourceCard({ source, label, icon }: { source: KnowledgeSource; label: string; icon: string }) {
  const { role } = useParams<{ role: string }>();
  const action = useSourceAction(source.id);
  const busy = action.sync.isPending;

  async function syncNow() {
    try {
      await action.sync.mutateAsync(source.status !== "active");
      toast.success(`Sync queued for ${source.name}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start the sync.");
    }
  }

  return (
    <Card>
      <CardContent className="grid gap-3 pt-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="rounded-md bg-neutral-100 p-2 dark:bg-neutral-800">
              <SourceIcon icon={icon} />
            </span>
            <div className="min-w-0">
              <Link href={`/${role}/knowledge-sources/${source.id}`} className="block truncate font-medium hover:underline">
                {source.name}
              </Link>
              <p className="text-xs text-neutral-500">{label}</p>
            </div>
          </div>
          <SourceStatusBadge status={source.status} />
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-neutral-500">
          <div>Documents: <span className="font-medium text-neutral-900 dark:text-neutral-100">{source.document_count}</span></div>
          <div>Failed: <span className={source.failed_count ? "font-medium text-red-600" : ""}>{source.failed_count}</span></div>
          <div>Last sync: {relativeTime(source.last_sync_at)}</div>
          <div>Next: {source.status === "active" && source.next_sync_at ? relativeTime(source.next_sync_at) : "—"}</div>
          <div className="col-span-2">Schedule: {source.sync_mode === "scheduled" ? intervalLabel(source.sync_interval_minutes) : source.sync_mode}</div>
        </dl>

        {source.last_sync_status && (
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            Last result: <RunStatusBadge status={source.last_sync_status as never} />
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button size="sm" loading={busy} onClick={syncNow}>
            {source.type === "web" ? "Crawl now" : "Sync now"}
          </Button>
          <Link href={`/${role}/knowledge-sources/${source.id}`}>
            <Button size="sm" variant="outline">Configure</Button>
          </Link>
          {source.status === "active" ? (
            <Button size="sm" variant="ghost" onClick={() => action.pause.mutate()}>
              Pause
            </Button>
          ) : source.status === "paused" ? (
            <Button size="sm" variant="ghost" onClick={() => action.resume.mutate()}>
              Resume
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function KnowledgeSourcesView() {
  const { role } = useParams<{ role: string }>();
  const sources = useKnowledgeSources();
  const types = useSourceTypes();
  const typeInfo = new Map((types.data?.types ?? []).map((t) => [t.type, t]));

  return (
    <div>
      <PageHeader
        title="Knowledge Sources"
        description="Connect external systems and websites. Content is discovered, versioned, chunked and indexed automatically, with its permissions and original links kept."
        actions={
          <Link href={`/${role}/knowledge-sources/new`}>
            <Button>
              <Plus className="h-4 w-4" />
              Add source
            </Button>
          </Link>
        }
      />

      <Summary />

      {sources.isError ? (
        <QueryError error={sources.error} onRetry={() => void sources.refetch()} />
      ) : sources.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !sources.data || sources.data.sources.length === 0 ? (
        <EmptyState icon={Database} title="No knowledge sources yet" description="Add a website, Wikipedia articles, Confluence, SharePoint or Teams." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sources.data.sources.map((source) => (
            <SourceCard
              key={source.id}
              source={source}
              label={typeInfo.get(source.type)?.display_name ?? source.type_label}
              icon={typeInfo.get(source.type)?.icon ?? "database"}
            />
          ))}
        </div>
      )}

      <p className="mt-6 text-xs text-neutral-400">
        <Badge variant="outline">Uploads</Badge> are managed under Documents; uploaded files and connected sources are searched together.
      </p>
    </div>
  );
}
