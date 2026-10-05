"use client";

import { useQuery } from "@tanstack/react-query";
import { Flag, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCreateFeatureFlag, useDeleteFeatureFlag, useFeatureFlags, useTenant, useToggleFeatureFlag } from "@/hooks/use-api";

interface DirectoryTenant {
  internalId: string;
  name: string;
}

async function json<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error ?? "Request failed.");
  return body as T;
}

// Same tolerant unwrap as the Tenants/Settings pages: the IAM gateway wraps as { success, data },
// the BFF wraps that again as { data }.
function asTenants(value: unknown): DirectoryTenant[] {
  const inner = (value as { data?: unknown })?.data ?? value;
  if (Array.isArray(inner)) return inner as DirectoryTenant[];
  const nested = (inner as { data?: unknown })?.data;
  return Array.isArray(nested) ? (nested as DirectoryTenant[]) : [];
}

/** Lets an admin pick a tenant by name instead of pasting a raw UUID — reuses the same real
 * directory the Tenants page shows, rather than making this the one place that still needs one
 * typed in blind. */
function useTenantDirectory() {
  return useQuery({
    queryKey: ["tenant-directory"],
    queryFn: async () => asTenants(await json<unknown>("/api/iam/tenants?page=1&limit=100")),
    retry: false,
  });
}

/** Resolves a tenant id to its real name, falling back to a truncated id only while loading or
 * if IAM can't be reached for it — same idiom as Documents' "Uploaded by" and the Tenants page. */
function ScopeBadge({ tenantId }: { tenantId: string }) {
  const { data: tenant, isLoading } = useTenant(tenantId);
  return (
    <Badge variant="outline">
      {isLoading ? "…" : (tenant?.name ?? <code className="text-xs">{tenantId.slice(0, 8)}…</code>)}
    </Badge>
  );
}

export function FeatureFlagsView() {
  const { data, isLoading } = useFeatureFlags();
  const directory = useTenantDirectory();
  const createFlag = useCreateFeatureFlag();
  const toggleFlag = useToggleFeatureFlag();
  const deleteFlag = useDeleteFeatureFlag();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ key: "", tenant_id: "", description: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createFlag.mutateAsync({
        key: form.key,
        tenant_id: form.tenant_id.trim() || null,
        enabled: false,
        description: form.description || null,
      });
      toast.success("Feature flag created.");
      setOpen(false);
      setForm({ key: "", tenant_id: "", description: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create feature flag.");
    }
  }

  async function handleToggle(id: string, next: boolean) {
    try {
      await toggleFlag.mutateAsync({ id, enabled: next });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not toggle feature flag.");
    }
  }

  return (
    <div>
      <PageHeader
        title="Feature Flags"
        description="Dynamic toggles, no redeploy needed. A tenant ID scopes an override; leave it blank for the global default."
        actions={<Button onClick={() => setOpen(true)}>New flag</Button>}
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.feature_flags.length === 0 ? (
        <EmptyState
          icon={Flag}
          title="No feature flags yet"
          description="Create one to control app behavior without a redeploy."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.feature_flags.map((flag) => (
              <TableRow key={flag.id}>
                <TableCell className="font-medium">{flag.key}</TableCell>
                <TableCell>
                  {flag.tenant_id ? (
                    <ScopeBadge tenantId={flag.tenant_id} />
                  ) : (
                    <Badge variant="secondary">global</Badge>
                  )}
                </TableCell>
                <TableCell className="max-w-xs truncate text-neutral-600 dark:text-neutral-400">
                  {flag.description ?? "—"}
                </TableCell>
                <TableCell>
                  <Switch
                    checked={flag.enabled}
                    onCheckedChange={(next) => handleToggle(flag.id, next)}
                    disabled={toggleFlag.isPending}
                    aria-label={`Toggle ${flag.key}`}
                  />
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete ${flag.key}`}
                    disabled={deleteFlag.isPending}
                    onClick={async () => {
                      if (!confirm(`Delete the flag "${flag.key}"? Its value falls back to the default.`)) return;
                      try {
                        await deleteFlag.mutateAsync(flag.id);
                        toast.success("Feature flag deleted.");
                      } catch (err) {
                        toast.error(err instanceof Error ? err.message : "Could not delete the flag.");
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New feature flag">
        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Key</Label>
            <Input
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              placeholder="enable_rbac"
              required
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Scope</Label>
            <Select
              value={form.tenant_id}
              onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
            >
              <option value="">Global default</option>
              {directory.data?.map((t) => (
                <option key={t.internalId} value={t.internalId}>
                  {t.name}
                </option>
              ))}
            </Select>
            {directory.isError && (
              <p className="text-xs text-amber-600">
                Could not load the tenant directory — only a global flag can be created right now.
              </p>
            )}
          </div>
          <div className="grid gap-1.5">
            <Label>Description</Label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <Button type="submit" loading={createFlag.isPending}>
            Create
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
