"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Select } from "@/components/ui/select";
import { useTenant } from "@/hooks/use-api";
import { useSession } from "@/lib/session";

interface Workspace {
  id: string;
  name: string;
  slug: string;
  roles: string[];
}

function asWorkspaces(payload: unknown): Workspace[] {
  const inner = (payload as { data?: unknown } | null)?.data ?? payload;
  const list = Array.isArray(inner) ? inner : ((inner as { data?: unknown } | null)?.data ?? []);
  return Array.isArray(list) ? (list as Workspace[]) : [];
}

/**
 * Shows the current workspace and, for someone who belongs to more than one (for
 * example after accepting an invitation into a second workspace), lets them switch.
 * Switching swaps the session cookies and reloads so every screen refetches.
 */
export function WorkspaceSwitcher() {
  const { session } = useSession();
  const [switching, setSwitching] = useState(false);

  const { data: workspaces = [] } = useQuery({
    queryKey: ["my-workspaces", session?.userId],
    queryFn: async () => {
      const res = await fetch("/api/iam/tenants/mine");
      if (!res.ok) return [];
      return asWorkspaces(await res.json());
    },
    enabled: !!session,
    staleTime: 60_000,
  });

  // Real per-id name resolution (via IAM's GET /tenants/:id, the only lookup it actually
  // has — no "list my tenants" endpoint exists), used as the fallback below when the
  // multi-workspace list above is unavailable (true for everyone today: no real backend
  // route yet serves /api/iam/tenants/mine) or only has the one tenant a JWT already names.
  const { data: resolvedCurrent } = useTenant(session?.tenantId);

  if (!session) return null;

  const current = workspaces.find((w) => w.id === session.tenantId);

  // One workspace (or the list is unavailable): just show where you are.
  if (workspaces.length < 2) {
    return (
      <span className="text-xs text-neutral-500">
        Workspace:{" "}
        <span className="font-medium text-neutral-700 dark:text-neutral-300">
          {current?.name ?? resolvedCurrent?.name ?? session.tenantId}
        </span>
      </span>
    );
  }

  async function switchTo(tenantId: string) {
    if (tenantId === session?.tenantId) return;
    setSwitching(true);
    try {
      const res = await fetch("/api/auth/switch-workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenantId }),
      });
      const json = await res.json().catch(() => null);
      if (!res.ok) throw new Error(json?.error ?? "Could not switch workspace.");
      // Full reload: the tenant is part of the token and of every cached query.
      window.location.assign("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not switch workspace.");
      setSwitching(false);
    }
  }

  return (
    <label className="flex items-center gap-2 text-xs text-neutral-500">
      Workspace:
      <Select
        className="h-7 w-52 py-0 text-xs"
        value={session.tenantId}
        disabled={switching}
        onChange={(e) => void switchTo(e.target.value)}
        aria-label="Switch workspace"
      >
        {workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </Select>
    </label>
  );
}
