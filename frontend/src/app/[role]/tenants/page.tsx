"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTenant } from "@/hooks/use-api";
import { useSession } from "@/lib/session";
import { formatDateTime } from "@/lib/utils";
import { Building2 } from "lucide-react";

const HISTORY_KEY = "rag-console-tenant-history";

interface IamTenant {
  internalId: string;
  publicId: string;
  name: string;
  slug: string;
  isActive: boolean;
  isDefault: boolean;
  createdAt: string;
}

async function json<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error ?? "Request failed.");
  return body as T;
}

// Same tolerant unwrap as the Settings page: the IAM gateway wraps as { success, data }, the
// BFF wraps that again as { data }.
function asTenants(value: unknown): IamTenant[] {
  const inner = (value as { data?: unknown })?.data ?? value;
  if (Array.isArray(inner)) return inner as IamTenant[];
  const nested = (inner as { data?: unknown })?.data;
  return Array.isArray(nested) ? (nested as IamTenant[]) : [];
}

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

  const directory = useQuery({
    queryKey: ["tenant-directory"],
    queryFn: async () => asTenants(await json<unknown>("/api/iam/tenants?page=1&limit=100")),
    retry: false,
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
      <PageHeader title="Tenants" description="Every organization on the platform, and which one you're currently browsing as." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Directory</CardTitle>
        </CardHeader>
        <CardContent>
          {directory.isError ? (
            <QueryError
              error={directory.error}
              onRetry={() => void directory.refetch()}
              message="Could not load the tenant directory — IAM's GET /tenants needs tenant:read_all, which only super_admin has today. The switcher below still works by ID regardless."
            />
          ) : directory.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : !directory.data || directory.data.length === 0 ? (
            <EmptyState icon={Building2} title="No tenants found" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {directory.data.map((t) => (
                  <TableRow key={t.internalId}>
                    <TableCell>
                      <div className="font-medium">{t.name}</div>
                      {t.isDefault && <div className="text-xs text-neutral-400">default</div>}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-neutral-500">{t.slug}</TableCell>
                    <TableCell>
                      <Badge variant={t.isActive ? "success" : "outline"}>{t.isActive ? "active" : "inactive"}</Badge>
                    </TableCell>
                    <TableCell className="text-neutral-500">{formatDateTime(t.createdAt)}</TableCell>
                    <TableCell>
                      <Button size="sm" variant="outline" onClick={() => switchTo(t.internalId)}>
                        Browse as
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Switch by ID</CardTitle>
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
