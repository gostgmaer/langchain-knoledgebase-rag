"use client";

import { useState } from "react";
import { toast } from "sonner";

import { QueryError } from "@/components/shared/query-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDeleteMapping, useIdentityMappings, useSaveMapping, useSourcePermissions } from "@/hooks/use-api";
import type { KnowledgeSource } from "@/lib/api/types";

/**
 * How the source's permissions become platform access. External ids are never assumed to equal internal ones:
 * an unmapped user or group grants nothing, so a document restricted to them is administrator-only until mapped.
 */
export function PermissionsTab({ source }: { source: KnowledgeSource }) {
  const perms = useSourcePermissions(source.id);
  const mappings = useIdentityMappings(source.type);
  const save = useSaveMapping();
  const remove = useDeleteMapping();
  const [draft, setDraft] = useState<{ key: string; internalType: "user" | "role"; internalId: string }>({ key: "", internalType: "role", internalId: "" });

  if (perms.isError) return <QueryError error={perms.error} onRetry={() => void perms.refetch()} />;
  if (perms.isLoading || !perms.data) return <Skeleton className="h-40 w-full" />;
  const p = perms.data;

  async function map(principalType: string, externalId: string, internalType: "user" | "role", internalId: string) {
    try {
      await save.mutateAsync({ provider: source.type, principal_type: principalType === "user" ? "user" : "group", external_id: externalId, internal_type: internalType, internal_id: internalId.trim() });
      toast.success("Mapped. Access on existing documents was updated.");
      setDraft({ key: "", internalType: "role", internalId: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the mapping.");
    }
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Access behaviour</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-1 text-sm">
          <p>
            Mode: <Badge variant="secondary">{p.permission_mode === "sync_external" ? "follow the source's permissions" : "use the default below"}</Badge>
            {!p.supports_external_permissions && <span className="ml-2 text-xs text-neutral-500">(this connector does not read permissions)</span>}
          </p>
          <p>Default visibility: <Badge variant="outline">{p.default_visibility === "restricted" ? `administrators${p.default_allowed_roles.length ? ` + ${p.default_allowed_roles.join(", ")}` : ""}` : "all members"}</Badge></p>
          <p className="text-xs text-neutral-500">{p.restricted_documents} document(s) from this source are restricted. Change the mode or default on the Configuration tab.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Not mapped yet ({p.unmapped_principals.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {p.unmapped_principals.length === 0 ? (
            <p className="text-sm text-neutral-500">Every user and group the source refers to is mapped (or none has been seen yet).</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>External {`user / group`}</TableHead>
                  <TableHead>Documents</TableHead>
                  <TableHead>Map to</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {p.unmapped_principals.map((u) => (
                  <UnmappedRow key={`${u.principal_type}:${u.external_id}`} principal={u} onMap={map} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Identity mappings for {source.type_label}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {mappings.data && mappings.data.mappings.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>External</TableHead>
                  <TableHead>Internal</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.data.mappings.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>{m.principal_type} <code className="text-xs">{m.external_id}</code></TableCell>
                    <TableCell>{m.internal_type} <code className="text-xs">{m.internal_id}</code></TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => m.id && remove.mutate(m.id)}>Remove</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-neutral-500">No mappings yet.</p>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <Input className="h-8 w-64 text-xs" placeholder="external group or user id" value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} aria-label="External id" />
            <Select className="h-8 w-28 text-xs" value={draft.internalType} onChange={(e) => setDraft({ ...draft, internalType: e.target.value as "user" | "role" })} aria-label="Internal type">
              <option value="role">role</option>
              <option value="user">user id</option>
            </Select>
            <Input className="h-8 w-48 text-xs" placeholder={draft.internalType === "role" ? "internal role, e.g. finance" : "internal user id"} value={draft.internalId} onChange={(e) => setDraft({ ...draft, internalId: e.target.value })} aria-label="Internal id" />
            <Button size="sm" disabled={!draft.key.trim() || !draft.internalId.trim()} onClick={() => void map("group", draft.key.trim(), draft.internalType, draft.internalId)}>
              Add mapping
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function UnmappedRow({ principal, onMap }: { principal: { principal_type: string; external_id: string; documents: number }; onMap: (t: string, id: string, internalType: "user" | "role", internalId: string) => Promise<void> }) {
  const [internalType, setInternalType] = useState<"user" | "role">(principal.principal_type === "user" ? "user" : "role");
  const [internalId, setInternalId] = useState("");
  return (
    <TableRow>
      <TableCell>{principal.principal_type} <code className="text-xs">{principal.external_id}</code></TableCell>
      <TableCell>{principal.documents}</TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <Select className="h-8 w-24 text-xs" value={internalType} onChange={(e) => setInternalType(e.target.value as "user" | "role")} aria-label="Internal type">
            <option value="role">role</option>
            <option value="user">user id</option>
          </Select>
          <Input className="h-8 w-40 text-xs" value={internalId} onChange={(e) => setInternalId(e.target.value)} placeholder="internal id" aria-label="Internal id" />
          <Button size="sm" disabled={!internalId.trim()} onClick={() => void onMap(principal.principal_type, principal.external_id, internalType, internalId)}>Map</Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
