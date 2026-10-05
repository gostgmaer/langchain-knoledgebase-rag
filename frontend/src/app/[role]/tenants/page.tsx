"use client";

import { Building2 } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTenantDirectory } from "@/hooks/use-tenant-directory";
import { useSession } from "@/lib/session";
import { formatDateTime } from "@/lib/utils";

const HISTORY_KEY = "rag-console-tenant-history";

export default function TenantsPage() {
  const { setViewingTenant } = useSession();
  const directory = useTenantDirectory();
  // Lazy initial state (this page renders only after the session has loaded on the client),
  // rather than copying localStorage into state from an effect. Stores ids (the real switching
  // mechanism needs one) but is only ever rendered back out by resolving each id to its name
  // against `directory.data` below — never as raw text (docs/BUGS.md item 34).
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
    const next = [tenantId, ...history.filter((h) => h !== tenantId)].slice(0, 8);
    setHistory(next);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  }

  const recentlyViewed = history
    .map((id) => directory.data?.find((t) => t.internalId === id))
    .filter((t): t is NonNullable<typeof t> => !!t);

  return (
    <div>
      <PageHeader title="Tenants" description="Every organization on the platform, and which one you're currently browsing as." />

      <Card>
        <CardHeader>
          <CardTitle>Directory</CardTitle>
        </CardHeader>
        <CardContent>
          {directory.isError ? (
            <QueryError
              error={directory.error}
              onRetry={() => void directory.refetch()}
              message="Could not load the tenant directory — IAM's GET /tenants needs tenant:read_all, which only super_admin has today."
            />
          ) : directory.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : !directory.data || directory.data.length === 0 ? (
            <EmptyState icon={Building2} title="No tenants found" />
          ) : (
            <>
              {recentlyViewed.length > 0 && (
                <div className="mb-4">
                  <p className="mb-2 text-xs font-medium text-neutral-500">Recently viewed</p>
                  <div className="flex flex-wrap gap-2">
                    {recentlyViewed.map((t) => (
                      <button
                        key={t.internalId}
                        onClick={() => switchTo(t.internalId)}
                        className="rounded-md border border-neutral-200 px-2 py-1 text-xs hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-900"
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
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
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
