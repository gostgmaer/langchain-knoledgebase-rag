"use client";

import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTenant } from "@/hooks/use-api";
import { useSession } from "@/lib/session";

const HISTORY_KEY = "rag-console-tenant-history";

/** One "recently viewed" pill — resolves its own real name, falling back to the raw id
 * while loading or if IAM can't be reached for it. */
function TenantHistoryButton({ id, onSelect }: { id: string; onSelect: (id: string) => void }) {
  const { data: tenant } = useTenant(id);
  return (
    <button
      onClick={() => onSelect(id)}
      className="rounded-md border border-neutral-200 px-2 py-1 text-xs hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
      title={id}
    >
      {tenant?.name ?? <span className="font-mono">{id}</span>}
    </button>
  );
}

export default function TenantsPage() {
  const { session, setViewingTenant } = useSession();
  const [draft, setDraft] = useState(session?.tenantId ?? "");
  // Lazy initial state (this page renders only after the session has loaded on the client),
  // rather than copying localStorage into state from an effect.
  const [history, setHistory] = useState<string[]>(() => {
    try {
      const raw = typeof window === "undefined" ? null : window.localStorage.getItem(HISTORY_KEY);
      const value = raw ? JSON.parse(raw) : [];
      return Array.isArray(value) ? value : [];
    } catch {
      return [];
    }
  });

  function switchTo(tenantId: string) {
    setViewingTenant(tenantId);
    setDraft(tenantId);
    const next = [tenantId, ...history.filter((h) => h !== tenantId)].slice(0, 8);
    setHistory(next);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  }

  return (
    <div>
      <PageHeader title="Tenants" description="Cross-tenant browsing for platform operators." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>A real limit, worth being upfront about</CardTitle>
          <CardDescription>
            IAM (the system of record for organizations) has no endpoint that lists every tenant
            across the platform — only a by-id lookup, which this page uses to show real names
            instead of raw ids wherever it already knows one. Every resource route (documents,
            agents, knowledge bases, ...) is scoped by whichever{" "}
            <code className="rounded bg-neutral-100 px-1 dark:bg-neutral-800">X-Tenant-ID</code>{" "}
            header is sent. This page can only switch which single tenant you&apos;re currently
            browsing as, one ID at a time — it can&apos;t show you a real directory of every
            tenant to pick from.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Switch tenant</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              switchTo(draft.trim());
            }}
          >
            <div className="grid flex-1 gap-1.5">
              <Label>Tenant ID</Label>
              <Input value={draft} onChange={(e) => setDraft(e.target.value)} className="font-mono" />
            </div>
            <Button type="submit">Switch</Button>
          </form>

          {history.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-medium text-neutral-500">Recently viewed</p>
              <div className="flex flex-wrap gap-2">
                {history.map((id) => (
                  <TenantHistoryButton key={id} id={id} onSelect={switchTo} />
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
