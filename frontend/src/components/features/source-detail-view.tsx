"use client";

import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { ConfigTab } from "@/components/sources/config-tab";
import { DocumentsTab } from "@/components/sources/documents-tab";
import { HistoryTab } from "@/components/sources/history-tab";
import { OverviewTab } from "@/components/sources/overview-tab";
import { PermissionsTab } from "@/components/sources/permissions-tab";
import { SourceIcon, SourceStatusBadge, intervalLabel } from "@/components/sources/common";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useKnowledgeSource, useSourceAction, useSourceTypes } from "@/hooks/use-api";

export function SourceDetailView({ sourceId }: { sourceId: string }) {
  const { role } = useParams<{ role: string }>();
  const router = useRouter();
  const source = useKnowledgeSource(sourceId);
  const types = useSourceTypes();
  const action = useSourceAction(sourceId);

  if (source.isError) return <QueryError error={source.error} onRetry={() => void source.refetch()} />;
  if (source.isLoading || !source.data) return <Skeleton className="h-64 w-full" />;

  const s = source.data;
  const type = types.data?.types.find((t) => t.type === s.type);

  async function remove() {
    if (!confirm(`Delete "${s.name}"? Its documents are archived (no longer used in answers) and its credentials are destroyed.`)) return;
    try {
      await action.remove.mutateAsync();
      toast.success("Source deleted.");
      router.push(`/${role}/knowledge-sources`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete the source.");
    }
  }

  return (
    <div>
      <PageHeader
        title={s.name}
        description={`${type?.display_name ?? s.type_label} · ${s.sync_mode === "scheduled" ? intervalLabel(s.sync_interval_minutes) : s.sync_mode} · ${s.document_count} documents`}
        actions={
          <div className="flex items-center gap-2">
            <SourceIcon icon={type?.icon ?? "database"} />
            <SourceStatusBadge status={s.status} />
            <Button variant="outline" size="sm" onClick={() => router.push(`/${role}/knowledge-sources`)}>Back</Button>
            <Button variant="destructive" size="sm" onClick={remove}>Delete</Button>
          </div>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="history">Sync history</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="permissions">Permissions</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab source={s} type={type} />
        </TabsContent>
        <TabsContent value="config">
          <ConfigTab source={s} type={type} catalogue={types.data} />
        </TabsContent>
        <TabsContent value="history">
          <HistoryTab sourceId={s.id} />
        </TabsContent>
        <TabsContent value="documents">
          <DocumentsTab sourceId={s.id} />
        </TabsContent>
        <TabsContent value="permissions">
          <PermissionsTab source={s} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
