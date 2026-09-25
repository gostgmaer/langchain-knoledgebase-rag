"use client";

import {
  BarChart3,
  Bot,
  Cpu,
  FileText,
  Flag,
  Gauge,
  LayoutDashboard,
  Library,
  MessageSquare,
  MessagesSquare,
  ScrollText,
  Settings,
  Search,
  ShieldCheck,
  UploadCloud,
  Users,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { notFound, usePathname } from "next/navigation";
import { use, type ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import type { NavItem } from "@/components/layout/sidebar";
import { SLUG_TO_ROLE, type Role } from "@/lib/session";

/**
 * One route tree (app/[role]/...) shared by all three roles instead
 * of three near-identical folders — the only thing that varies per
 * role is which of these nav items shows up and where "home" points.
 * Every feature page itself has no idea which role rendered it; it
 * derives basePath from the `role` URL segment it's already given.
 */
const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  customer: [
    { href: "/customer/chat", label: "Chat", icon: MessageSquare },
    { href: "/customer/settings", label: "Settings", icon: Settings },
  ],
  tenant_admin: [
    { href: "/tenant-admin", label: "Dashboard", icon: LayoutDashboard },
    { href: "/tenant-admin/chat", label: "Chat", icon: MessageSquare },
    { href: "/tenant-admin/agents", label: "Agents", icon: Bot },
    { href: "/tenant-admin/knowledge-bases", label: "Knowledge Bases", icon: Library },
    { href: "/tenant-admin/documents", label: "Documents", icon: FileText },
    { href: "/tenant-admin/search", label: "Search", icon: Search },
    { href: "/tenant-admin/prompts", label: "Prompts", icon: ScrollText },
    { href: "/tenant-admin/tools", label: "Tools", icon: Wrench },
    { href: "/tenant-admin/team", label: "Team", icon: Users },
    { href: "/tenant-admin/model-profiles", label: "Model Profiles", icon: Cpu },
    { href: "/tenant-admin/feedback", label: "Feedback", icon: MessagesSquare },
    { href: "/tenant-admin/upload-jobs", label: "Upload Jobs", icon: UploadCloud },
    { href: "/tenant-admin/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/tenant-admin/usage", label: "Usage", icon: Gauge },
    { href: "/tenant-admin/settings", label: "Settings", icon: Settings },
  ],
  admin: [
    { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
    { href: "/admin/tenants", label: "Tenants", icon: ShieldCheck },
    { href: "/admin/team", label: "Team", icon: Users },
    { href: "/admin/model-profiles", label: "Model Profiles", icon: Cpu },
    { href: "/admin/chat", label: "Chat", icon: MessageSquare },
    { href: "/admin/agents", label: "Agents", icon: Bot },
    { href: "/admin/knowledge-bases", label: "Knowledge Bases", icon: Library },
    { href: "/admin/documents", label: "Documents", icon: FileText },
    { href: "/admin/search", label: "Search", icon: Search },
    { href: "/admin/prompts", label: "Prompts", icon: ScrollText },
    { href: "/admin/tools", label: "Tools", icon: Wrench },
    { href: "/admin/feedback", label: "Feedback", icon: MessagesSquare },
    { href: "/admin/upload-jobs", label: "Upload Jobs", icon: UploadCloud },
    { href: "/admin/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/admin/usage", label: "Usage", icon: Gauge },
    { href: "/admin/feature-flags", label: "Feature Flags", icon: Flag },
    { href: "/admin/settings", label: "Settings", icon: Settings },
  ],
};

/**
 * A page is reachable only if it is in this role's own navigation (or a sub-page of one).
 * Hiding a link is not access control: without this a customer could open
 * /customer/analytics or /customer/feature-flags just by typing the URL.
 */
function isAllowedPath(pathname: string, slug: string, items: NavItem[]): boolean {
  const clean = pathname.replace(/\/+$/, "");
  if (clean === `/${slug}`) return true;
  return items.some((item) => clean === item.href || clean.startsWith(`${item.href}/`));
}

const HOME_BY_ROLE: Record<Role, string> = {
  customer: "/customer/chat",
  tenant_admin: "/tenant-admin",
  admin: "/admin",
};

export default function RoleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ role: string }>;
}) {
  const { role: slug } = use(params);
  const pathname = usePathname();
  const role = SLUG_TO_ROLE[slug];

  if (!role) notFound();

  const allowed = isAllowedPath(pathname, slug, NAV_BY_ROLE[role]);

  return (
    <AppShell role={role} navItems={NAV_BY_ROLE[role]} homeHref={HOME_BY_ROLE[role]}>
      {allowed ? (
        children
      ) : (
        <div className="mx-auto mt-16 max-w-md space-y-3 text-center">
          <h1 className="text-lg font-semibold">You don&apos;t have access to this page</h1>
          <p className="text-sm text-muted-foreground">
            This page is not part of your role. Use the menu, or ask a workspace admin if you need it.
          </p>
          <Link href={HOME_BY_ROLE[role]} className="text-sm underline">
            Go to your home page
          </Link>
        </div>
      )}
    </AppShell>
  );
}
