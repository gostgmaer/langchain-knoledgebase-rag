"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useSession } from "@/lib/session";

interface Role {
  id: string;
  name: string;
}

interface Invitation {
  id: string;
  email: string;
  roleId: string;
  status: string;
  createdAt: string;
  expiresAt: string;
}

// Roles that make no sense to hand out from an invite form: platform-wide
// operators and machine identities aren't teammates. IAM still decides what
// the inviter is actually allowed to grant.
const HIDDEN_ROLES = new Set(["super_admin", "service_account"]);

async function iam<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/iam/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new Error(json?.error ?? "Request failed.");
  return json.data as T;
}

const asList = <T,>(value: unknown): T[] =>
  Array.isArray(value) ? value : Array.isArray((value as { items?: T[] })?.items) ? (value as { items: T[] }).items : [];

export default function TeamPage() {
  const { session } = useSession();
  const tenantId = session?.tenantId;
  const queryClient = useQueryClient();

  const [email, setEmail] = useState("");
  const [pickedRoleId, setPickedRoleId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const rolesQuery = useQuery({
    queryKey: ["team-roles"],
    queryFn: async () => asList<Role>(await iam<unknown>("rbac/roles")).filter((r) => !HIDDEN_ROLES.has(r.name)),
  });
  const roles = useMemo(() => rolesQuery.data ?? [], [rolesQuery.data]);

  const invitationsKey = ["team-invitations", tenantId];
  const invitationsQuery = useQuery({
    queryKey: invitationsKey,
    enabled: !!tenantId,
    queryFn: async () => asList<Invitation>(await iam<unknown>(`tenants/${encodeURIComponent(tenantId!)}/invitations`)),
  });
  const invitations = invitationsQuery.data ?? [];

  const roleName = useMemo(() => new Map(roles.map((r) => [r.id, r.name])), [roles]);
  // "member" is the ordinary-teammate default when it exists; an explicit pick wins.
  const roleId = pickedRoleId || roles.find((r) => r.name === "member")?.id || roles[0]?.id || "";

  const inviteMutation = useMutation({
    mutationFn: (vars: { email: string; roleId: string }) =>
      iam(`tenants/${encodeURIComponent(tenantId!)}/invite`, { method: "POST", body: JSON.stringify(vars) }),
    onSuccess: (_data, vars) => {
      setNotice(`Invitation sent to ${vars.email}.`);
      setEmail("");
      return queryClient.invalidateQueries({ queryKey: invitationsKey });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) =>
      iam(`tenants/${encodeURIComponent(tenantId!)}/invitations/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invitationsKey }),
  });

  const error = [rolesQuery.error, invitationsQuery.error, inviteMutation.error, revokeMutation.error]
    .filter((e): e is Error => e instanceof Error)
    .map((e) => e.message)[0];

  function invite(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setNotice(null);
    inviteMutation.mutate({ email: email.trim(), roleId });
  }

  return (
    <div>
      <PageHeader title="Team" description="Invite people to this workspace and manage pending invitations." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Invite a teammate</CardTitle>
          <CardDescription>
            They get an email with a link. New people create an account (or sign in with Google,
            Microsoft or Facebook using the same address); people who already have an account just
            accept. Invitations expire after 7 days.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-wrap items-end gap-3" onSubmit={invite}>
            <div className="grid min-w-64 flex-1 gap-1.5">
              <Label htmlFor="invite-email">Email</Label>
              <Input id="invite-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="grid w-48 gap-1.5">
              <Label htmlFor="invite-role">Role</Label>
              <Select id="invite-role" value={roleId} onChange={(e) => setPickedRoleId(e.target.value)} required>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" loading={inviteMutation.isPending} disabled={!tenantId || !roleId}>
              Send invite
            </Button>
          </form>
          {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
          {notice && <p className="mt-3 text-sm text-green-700 dark:text-green-400">{notice}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Invitations</CardTitle>
        </CardHeader>
        <CardContent>
          {invitations.length === 0 ? (
            <p className="text-sm text-neutral-500">No invitations yet.</p>
          ) : (
            <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
              {invitations.map((inv) => (
                <li key={inv.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{inv.email}</p>
                    <p className="text-xs text-neutral-500">
                      {roleName.get(inv.roleId) ?? "role"} · expires {new Date(inv.expiresAt).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge>{inv.status.toLowerCase()}</Badge>
                    {inv.status.toUpperCase() === "PENDING" && (
                      <Button size="sm" variant="outline" onClick={() => revokeMutation.mutate(inv.id)}>
                        Revoke
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
