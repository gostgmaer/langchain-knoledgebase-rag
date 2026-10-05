"use client";

import { Check, Copy, Key } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
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
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/hooks/use-api";
import type { CreateApiKeyResponse } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

export function ApiKeysView() {
  const { data, isLoading, isError, error, refetch } = useApiKeys();
  const createKey = useCreateApiKey();
  const revokeKey = useRevokeApiKey();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<CreateApiKeyResponse | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const result = await createKey.mutateAsync({ name });
      setCreated(result);
      setOpen(false);
      setName("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create API key.");
    }
  }

  async function handleRevoke(id: string, keyName: string) {
    try {
      await revokeKey.mutateAsync(id);
      toast.success(`"${keyName}" revoked — it can no longer authenticate anything.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not revoke the key.");
    }
  }

  return (
    <div>
      <PageHeader
        title="API Keys"
        description="Programmatic access to this API, independent of a browser session — send one as Authorization: Bearer <key>. Each key acts with full admin access to this tenant."
        actions={<Button onClick={() => setOpen(true)}>New API key</Button>}
      />

      {isError ? (
        <QueryError error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : !data || data.api_keys.length === 0 ? (
        <EmptyState icon={Key} title="No API keys yet" description="Create one to call this API without a browser session." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Created by</TableHead>
              <TableHead>Last used</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.api_keys.map((k) => (
              <TableRow key={k.id}>
                <TableCell className="font-medium">{k.name}</TableCell>
                <TableCell>
                  <code className="text-xs text-neutral-500">{k.key_prefix}…</code>
                </TableCell>
                <TableCell className="text-neutral-500">{k.created_by_email}</TableCell>
                <TableCell className="text-neutral-500">
                  {k.last_used_at ? formatDateTime(k.last_used_at) : "never"}
                </TableCell>
                <TableCell>
                  <Badge variant={k.is_active ? "success" : "outline"}>{k.is_active ? "active" : "revoked"}</Badge>
                </TableCell>
                <TableCell>
                  {k.is_active && (
                    <Button size="sm" variant="outline" onClick={() => handleRevoke(k.id, k.name)}>
                      Revoke
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New API key">
        <form onSubmit={handleCreate} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. CI pipeline, Zapier integration"
              required
            />
          </div>
          <Button type="submit" loading={createKey.isPending}>
            Create
          </Button>
        </form>
      </Dialog>

      {created && <RevealKeyDialog result={created} onClose={() => setCreated(null)} />}
    </div>
  );
}

function RevealKeyDialog({ result, onClose }: { result: CreateApiKeyResponse; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Could not copy automatically — select and copy the key manually.");
    }
  }

  return (
    <Dialog open onClose={onClose} title={`"${result.name}" created`}>
      <div className="grid gap-4">
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm">
          This is the only time the real key is shown. Copy it now — it can&apos;t be retrieved again.
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 overflow-x-auto rounded-md border bg-neutral-50 px-3 py-2 text-xs dark:bg-neutral-900">
            {result.key}
          </code>
          <Button type="button" size="icon" variant="outline" onClick={copy} aria-label="Copy key">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
        <Button onClick={onClose}>Done</Button>
      </div>
    </Dialog>
  );
}
