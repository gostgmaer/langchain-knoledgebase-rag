"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Sidebar, type NavItem } from "@/components/layout/sidebar";
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
  const { session, isLoading } = useSession();

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
