"use client";

import { LogOut, Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { WorkspaceSwitcher } from "@/components/layout/workspace-switcher";
import { useHealth, useTenant } from "@/hooks/use-api";
import { ROLE_LABELS, useSession } from "@/lib/session";

export function Topbar({ onMenuClick }: { onMenuClick?: () => void }) {
  const router = useRouter();
  const { session, logout, setViewingTenant } = useSession();
  const { data: health } = useHealth();
  const { data: currentTenant } = useTenant(session?.tenantId);
  const [tenantDraft, setTenantDraft] = useState(session?.tenantId ?? "");

  if (!session) return null;

  const healthy = health?.status === "healthy";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-neutral-200 bg-white px-3 sm:px-5 dark:border-neutral-800 dark:bg-neutral-950">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open menu"
          className="shrink-0 rounded-md p-1.5 text-neutral-500 hover:bg-neutral-100 lg:hidden dark:hover:bg-neutral-900"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Badge variant="secondary" className="hidden sm:inline-flex">
          {ROLE_LABELS[session.role]}
        </Badge>
        {session.role === "admin" ? (
          <form
            className="hidden min-w-0 items-center gap-2 md:flex"
            onSubmit={(e) => {
              e.preventDefault();
              setViewingTenant(tenantDraft.trim());
            }}
          >
            <span className="shrink-0 text-xs text-neutral-500">Viewing tenant:</span>
            <span className="truncate text-xs font-medium text-neutral-700 dark:text-neutral-300">
              {currentTenant?.name ?? session.tenantId}
            </span>
            <Input
              value={tenantDraft}
              onChange={(e) => setTenantDraft(e.target.value)}
              placeholder="Switch to a different tenant ID…"
              className="h-7 w-48 shrink-0 font-mono text-xs lg:w-64"
            />
            <Button type="submit" size="sm" variant="outline" className="shrink-0">
              Switch
            </Button>
          </form>
        ) : (
          <div className="min-w-0">
            <WorkspaceSwitcher />
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:gap-4">
        <span className="hidden items-center gap-1.5 text-xs text-neutral-500 sm:flex">
          <span
            className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-success" : "bg-neutral-300 dark:bg-neutral-700"}`}
          />
          {health ? (healthy ? "Backend healthy" : "Backend unreachable") : "Checking backend…"}
        </span>
        <span className="hidden max-w-32 truncate text-sm font-medium sm:block lg:max-w-none">
          {session.displayName}
        </span>
        <ThemeToggle />
        <Button
          variant="ghost"
          size="icon"
          onClick={async () => {
            await logout();
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
