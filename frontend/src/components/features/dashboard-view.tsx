"use client";

import { QueryError } from "@/components/shared/query-error";
import { Bot, Database, FileText, Library, MessagesSquare, Plug } from "lucide-react";
import Link from "next/link";

import { ChunkingBadge } from "@/components/documents/chunking-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAgents,
  useDocuments,
  useFeedbackList,
  useHealth,
  useKnowledgeBases,
  useObservabilitySummary,
  useSourcesSummary,
  useTenant,
  useUsage,
} from "@/hooks/use-api";
import { useSession } from "@/lib/session";
import { formatDateTime } from "@/lib/utils";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);
const ms = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v)} ms`);
const compactNumber = new Intl.NumberFormat("en-US", { notation: "compact" });

function formatCost(cost: string | undefined): string {
  if (cost === undefined) return "—";
  const n = Number(cost);
  return `$${n < 0.01 && n > 0 ? n.toFixed(6) : n.toFixed(2)}`;
}

export function DashboardView({ basePath }: { basePath: string }) {
  const { session } = useSession();
  const { data: health } = useHealth();
  const { data: tenant } = useTenant(session?.tenantId);
  const { data: documents, isError: documentsFailed } = useDocuments();
  const { data: knowledgeBases, isError: knowledgeBasesFailed } = useKnowledgeBases();
  const { data: agents, isError: agentsFailed } = useAgents();
  const { data: feedback, isError: feedbackFailed } = useFeedbackList();
  const { data: usage, isError: usageFailed } = useUsage(30);
  const { data: observability, isError: observabilityFailed } = useObservabilitySummary(7);
  const { data: sources, isError: sourcesFailed } = useSourcesSummary();
  const someFailed =
    documentsFailed ||
    knowledgeBasesFailed ||
    agentsFailed ||
    feedbackFailed ||
    usageFailed ||
    observabilityFailed ||
    sourcesFailed;

  const stats = [
    { label: "Documents", value: documents?.total ?? "—", href: `${basePath}/documents`, icon: FileText },
    { label: "Knowledge Bases", value: knowledgeBases?.total ?? "—", href: `${basePath}/knowledge-bases`, icon: Library },
    { label: "Agents", value: agents?.total ?? "—", href: `${basePath}/agents`, icon: Bot },
    { label: "Feedback", value: feedback?.total ?? "—", href: `${basePath}/feedback`, icon: MessagesSquare },
  ];

  const recentDocuments = (documents?.documents ?? []).filter((d) => d.is_current && d.status !== "ARCHIVED").slice(0, 5);

  return (
    <div>
      {someFailed && (
        <div className="mb-4">
          <QueryError message="Some dashboard figures could not be loaded." />
        </div>
      )}
      <PageHeader
        title={`Welcome, ${session?.displayName ?? ""}`}
        description={`Browsing ${tenant?.name ?? (session?.tenantId ? "…" : "")}`}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(({ label, value, href, icon: Icon }) => (
          <Link key={label} href={href}>
            <Card className="transition-all hover:border-primary/30 hover:shadow-md">
              <CardContent className="flex items-center justify-between pt-5">
                <div>
                  <p className="text-xs text-neutral-500">{label}</p>
                  <p className="text-2xl font-semibold">{value}</p>
                </div>
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft">
                  <Icon className="h-5 w-5 text-primary" />
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Database className="h-4 w-4 text-neutral-400" />
              Usage, last 30 days
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 text-sm">
            <Stat label="Tokens" value={usage ? compactNumber.format(usage.total_tokens) : "—"} />
            <Stat label="Est. cost" value={formatCost(usage?.cost)} />
            <Stat label="Prompt" value={usage ? compactNumber.format(usage.prompt_tokens) : "—"} />
            <Stat label="Completion" value={usage ? compactNumber.format(usage.completion_tokens) : "—"} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Retrieval health, last 7 days</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 text-sm">
            <Stat label="Citation coverage" value={pct(observability?.retrieval.citation_coverage)} />
            <Stat label="Empty retrievals" value={pct(observability?.retrieval.empty_rate)} />
            <Stat label="Avg latency" value={ms(observability?.retrieval.avg_latency_ms)} />
            <Stat
              label="Needs attention"
              value={
                observability
                  ? `${observability.documents.stale_embeddings + observability.documents.never_retrieved}`
                  : "—"
              }
              hint="stale or never-retrieved documents"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Plug className="h-4 w-4 text-neutral-400" />
              Knowledge sources
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 text-sm">
            <Stat label="Connected" value={sources ? `${sources.connected_sources}` : "—"} />
            <Stat
              label="Needing attention"
              value={sources ? `${sources.sources_with_errors + sources.disconnected_sources}` : "—"}
            />
            <Stat label="Documents today" value={sources ? `+${sources.documents_added_today}` : "—"} />
            <Stat label="Failed" value={sources ? `${sources.failed_documents}` : "—"} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Recently uploaded documents</CardTitle>
          </CardHeader>
          <CardContent>
            {documents === undefined ? (
              <Skeleton className="h-32 w-full" />
            ) : recentDocuments.length === 0 ? (
              <EmptyState icon={FileText} title="No documents yet" description="Upload one to get started." />
            ) : (
              <ul className="divide-y divide-neutral-100 dark:divide-neutral-900">
                {recentDocuments.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-3 py-2.5 text-sm first:pt-0 last:pb-0">
                    <Link href={`${basePath}/documents/${d.id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
                      {d.file_name}
                    </Link>
                    <span className="flex shrink-0 items-center gap-2">
                      <ChunkingBadge chunking={d.chunking} />
                      <StatusBadge status={d.status} />
                      <span className="hidden text-xs text-neutral-400 sm:inline">{formatDateTime(d.created_at)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Backend health</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 text-sm">
            <HealthStat label="Service" value={health?.status} />
            <HealthStat label="Database" value={health?.database} />
            <HealthStat label="Redis" value={health?.redis} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-xs text-neutral-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold">{value}</p>
      {hint && <p className="text-xs text-neutral-400">{hint}</p>}
    </div>
  );
}

function HealthStat({ label, value }: { label: string; value?: string }) {
  const healthy = value === "healthy";
  const dotColor = value === undefined ? "bg-neutral-300 dark:bg-neutral-700" : healthy ? "bg-success" : "bg-danger";

  return (
    <div>
      <p className="text-xs text-neutral-500">{label}</p>
      <p className="mt-1 flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
        {value ?? "checking…"}
      </p>
    </div>
  );
}
