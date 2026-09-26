"use client";

import { useState } from "react";
import { toast } from "sonner";

import { ConfigForm } from "@/components/sources/config-form";
import { RunStatusBadge, duration, relativeTime } from "@/components/sources/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSourceAction, useSourceHealth, useSourceRuns } from "@/hooks/use-api";
import type { ConnectorType, KnowledgeSource } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-neutral-100 pb-2 text-sm last:border-0 dark:border-neutral-900">
      <span className="text-neutral-500">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}

export function OverviewTab({ source, type }: { source: KnowledgeSource; type: ConnectorType | undefined }) {
  const health = useSourceHealth(source.id);
  const runs = useSourceRuns(source.id, 1, 0);
  const action = useSourceAction(source.id);
  const latest = runs.data?.runs[0];
  const running = latest && (latest.status === "queued" || latest.status === "running");
  const [credentials, setCredentials] = useState<Record<string, unknown>>({});
  const h = health.data;

  async function guard(promise: Promise<unknown>, ok: string) {
    try {
      await promise;
      toast.success(ok);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "That did not work.");
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Connection health</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          <Row label="Connection" value={<Badge variant={h?.connection === "healthy" ? "success" : h?.connection === "unknown" ? "outline" : "destructive"}>{h?.connection ?? "…"}</Badge>} />
          <Row label="Authentication" value={<Badge variant={h?.authentication === "valid" ? "success" : h?.authentication === "unknown" ? "outline" : "destructive"}>{h?.authentication ?? "…"}</Badge>} />
          <Row label="Last successful sync" value={h ? relativeTime(h.last_successful_sync_at) : "…"} />
          <Row label="Last failed sync" value={h?.last_failed_sync_at ? `${relativeTime(h.last_failed_sync_at)}` : "none"} />
          {h?.last_failure && <p className="text-xs text-red-600">{h.last_failure}</p>}
          <Row label="Average sync time" value={duration(h?.avg_sync_seconds)} />
          <Row label="Documents discovered / indexed / failed" value={h ? `${h.documents_discovered} / ${h.documents_indexed} / ${h.documents_failed}` : "…"} />
          <Row label="API requests / retries / errors" value={h ? `${h.api.requests ?? "—"} / ${h.api.retries ?? "—"} / ${h.api.errors ?? "—"}` : "…"} />
          <Row label="Rate-limit hits" value={h?.api.rate_limited ?? "—"} />
          <Row label="API rate limit used" value={h?.rate_limit_used_percent != null ? `${h.rate_limit_used_percent}%` : "not reported"} />
          {h && h.warnings.length > 0 && <p className="text-xs text-amber-700">{h.warnings.slice(0, 3).join(" · ")}</p>}
          <div className="pt-2">
            <Button
              size="sm"
              variant="outline"
              loading={action.testSaved.isPending}
              onClick={() => void guard(action.testSaved.mutateAsync().then((r) => { if (!r.ok) throw new Error(r.message); }), "Connection works.")}
            >
              Test connection
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Synchronisation</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          <Row label="Last sync" value={latest ? <span className="flex items-center gap-2">{relativeTime(latest.started_at)} <RunStatusBadge status={latest.status} /></span> : "never"} />
          <Row label="Next sync" value={source.status === "active" && source.next_sync_at ? formatDateTime(source.next_sync_at) : "—"} />
          {latest && (
            <Row label="Latest result" value={`+${latest.documents_created} ~${latest.documents_updated} −${latest.documents_deleted} · ${latest.documents_skipped} unchanged · ${latest.documents_failed} failed`} />
          )}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button size="sm" loading={action.sync.isPending} disabled={!!running} onClick={() => void guard(action.sync.mutateAsync(source.status !== "active"), "Sync queued.")}>
              {type?.type === "web" ? "Crawl now" : "Sync now"}
            </Button>
            {running && (
              <Button size="sm" variant="outline" onClick={() => void guard(action.cancel.mutateAsync(), "Cancellation requested.")}>
                Stop sync
              </Button>
            )}
            {source.status === "active" ? (
              <Button size="sm" variant="ghost" onClick={() => void guard(action.pause.mutateAsync(), "Paused.")}>Pause</Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => void guard(action.resume.mutateAsync(), "Resumed.")}>Resume</Button>
            )}
          </div>
          {source.webhook_enabled && (
            <p className="pt-2 text-xs text-neutral-500">
              Webhook: <code>POST /api/v1/webhooks/sources/{source.id}</code> with header <code>X-Webhook-Secret</code>. Notifications queue a normal sync.
            </p>
          )}
        </CardContent>
      </Card>

      {type && type.credential_kind !== "none" && (
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Credentials</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <p className="text-sm">
              {source.credential.configured ? (
                <>Stored encrypted{source.credential.updated_at ? `, last set ${relativeTime(source.credential.updated_at)}` : ""}. The value is never shown.</>
              ) : source.credential.revoked ? (
                "Revoked. Set new credentials to reconnect."
              ) : (
                "None set."
              )}
            </p>
            <div className="max-w-xl">
              <ConfigForm idPrefix="rotate" fields={type.credential_fields} values={credentials} onChange={setCredentials} />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                loading={action.setCredentials.isPending}
                disabled={Object.keys(credentials).length === 0}
                onClick={() =>
                  void guard(action.setCredentials.mutateAsync(credentials).then(() => setCredentials({})), source.credential.configured ? "Credentials rotated." : "Credentials saved.")
                }
              >
                {source.credential.configured ? "Rotate credentials" : "Save credentials"}
              </Button>
              {source.credential.configured && (
                <Button size="sm" variant="outline" onClick={() => { if (confirm("Revoke the credentials? Syncing stops until new ones are set.")) void guard(action.revokeCredentials.mutateAsync(), "Credentials revoked."); }}>
                  Revoke
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
