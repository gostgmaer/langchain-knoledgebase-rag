"use client";

import { Flag } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useCreateFeatureFlag, useFeatureFlags, useToggleFeatureFlag } from "@/hooks/use-api";

export function FeatureFlagsView() {
  const { data, isLoading } = useFeatureFlags();
  const createFlag = useCreateFeatureFlag();
  const toggleFlag = useToggleFeatureFlag();
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.feature_flags.map((flag) => (
              <TableRow key={flag.id}>
                <TableCell className="font-medium">{flag.key}</TableCell>
                <TableCell>
                  {flag.tenant_id ? (
                    <Badge variant="outline">
                      <code className="text-xs">{flag.tenant_id.slice(0, 8)}…</code>
                    </Badge>
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
            <Label>Tenant ID (optional — blank means global default)</Label>
            <Input
              value={form.tenant_id}
              onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
              className="font-mono"
              placeholder="leave blank for global"
            />
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
