"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Sidebar, type NavItem } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Topbar } from "@/components/layout/topbar";
import { type Role, useSession } from "@/lib/session";

export function AppShell({
  role,
  navItems,
  homeHref,
  children,
}: {
  role: Role;
  navItems: NavItem[];
  homeHref: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const { session, isLoading, logout } = useSession();

  useEffect(() => {
    if (isLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    if (session.role !== role) {
      router.replace("/");
    }
  }, [isLoading, session, role, router]);

  if (isLoading || !session || session.role !== role) {
    return <div className="flex h-screen items-center justify-center text-sm text-neutral-400">Loading…</div>;
  }

  // An IAM account that belongs to no workspace has no tenant, so every API call
  // would be refused. Say so, instead of showing an app that silently fails.
  if (!session.tenantId) {
    return (
      <div className="flex h-screen items-center justify-center p-6">
        <div className="max-w-md space-y-4 rounded-lg border p-6 text-center">
          <h1 className="text-lg font-semibold">You are not in a workspace yet</h1>
          <p className="text-sm text-muted-foreground">
            Your session ({session.displayName}) is not attached to any workspace. If you were just added or invited,
            sign out and sign in again. Otherwise ask a workspace admin to invite this email address and open the link
            in the invitation email.
          </p>
          <Button variant="outline" onClick={() => void logout().then(() => router.replace("/"))}>
            Sign out
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar items={navItems} homeHref={homeHref} />
      <div className="flex h-screen flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
