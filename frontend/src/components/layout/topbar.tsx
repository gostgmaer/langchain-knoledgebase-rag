"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useHealth } from "@/hooks/use-api";
import { ROLE_LABELS, useSession } from "@/lib/session";

export function Topbar() {
  const router = useRouter();
  const { session, logout, setViewingTenant } = useSession();
  const { data: health } = useHealth();
  const [tenantDraft, setTenantDraft] = useState(session?.tenantId ?? "");

  if (!session) return null;

  const healthy = health?.status === "healthy";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-neutral-200 bg-white px-5 dark:border-neutral-800 dark:bg-neutral-950">
      <div className="flex items-center gap-3">
        <Badge variant="secondary">{ROLE_LABELS[session.role]}</Badge>
        {session.role === "admin" ? (
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setViewingTenant(tenantDraft.trim());
            }}
          >
            <span className="text-xs text-neutral-500">Viewing tenant:</span>
            <Input
              value={tenantDraft}
              onChange={(e) => setTenantDraft(e.target.value)}
              className="h-7 w-72 font-mono text-xs"
            />
            <Button type="submit" size="sm" variant="outline">
              Switch
            </Button>
          </form>
        ) : (
          <span className="font-mono text-xs text-neutral-400">tenant: {session.tenantId}</span>
        )}
      </div>

      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5 text-xs text-neutral-500">
          <span
            className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-emerald-500" : "bg-neutral-300 dark:bg-neutral-700"}`}
          />
          {health ? (healthy ? "Backend healthy" : "Backend unreachable") : "Checking backend…"}
        </span>
        <span className="text-sm font-medium">{session.displayName}</span>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            logout();
            router.push("/");
          }}
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
