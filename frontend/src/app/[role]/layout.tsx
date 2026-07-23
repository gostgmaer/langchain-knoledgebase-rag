"use client";

import {
  Bot,
  Cpu,
  FileText,
  LayoutDashboard,
  Library,
  MessageSquare,
  MessagesSquare,
  ScrollText,
  Search,
  ShieldCheck,
  UploadCloud,
  Wrench,
} from "lucide-react";
import { notFound } from "next/navigation";
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
  customer: [{ href: "/customer/chat", label: "Chat", icon: MessageSquare }],
  tenant_admin: [
    { href: "/tenant-admin", label: "Dashboard", icon: LayoutDashboard },
    { href: "/tenant-admin/chat", label: "Chat", icon: MessageSquare },
    { href: "/tenant-admin/agents", label: "Agents", icon: Bot },
    { href: "/tenant-admin/knowledge-bases", label: "Knowledge Bases", icon: Library },
    { href: "/tenant-admin/documents", label: "Documents", icon: FileText },
    { href: "/tenant-admin/search", label: "Search", icon: Search },
    { href: "/tenant-admin/prompts", label: "Prompts", icon: ScrollText },
    { href: "/tenant-admin/tools", label: "Tools", icon: Wrench },
    { href: "/tenant-admin/model-profiles", label: "Model Profiles", icon: Cpu },
    { href: "/tenant-admin/feedback", label: "Feedback", icon: MessagesSquare },
    { href: "/tenant-admin/upload-jobs", label: "Upload Jobs", icon: UploadCloud },
  ],
  admin: [
    { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
    { href: "/admin/tenants", label: "Tenants", icon: ShieldCheck },
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
  ],
};

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
  const role = SLUG_TO_ROLE[slug];

  if (!role) notFound();

  return (
    <AppShell role={role} navItems={NAV_BY_ROLE[role]} homeHref={HOME_BY_ROLE[role]}>
      {children}
    </AppShell>
  );
}
