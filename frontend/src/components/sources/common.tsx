import {
  BookOpen,
  Book,
  Cloud,
  Database,
  FolderKanban,
  Globe,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { SourceStatus, SyncRun } from "@/lib/api/types";

const ICONS: Record<string, LucideIcon> = {
  globe: Globe,
  "book-open": BookOpen,
  book: Book,
  "message-square": MessageSquare,
  "folder-kanban": FolderKanban,
  cloud: Cloud,
  database: Database,
};

export function SourceIcon({ icon, className }: { icon: string; className?: string }) {
  const Icon = ICONS[icon] ?? Database;
  return <Icon className={className ?? "h-5 w-5"} aria-hidden />;
}

const STATUS_VARIANT: Record<SourceStatus, BadgeProps["variant"]> = {
  active: "success",
  paused: "outline",
  error: "destructive",
  disconnected: "destructive",
};
const STATUS_LABEL: Record<SourceStatus, string> = {
  active: "Connected",
  paused: "Paused",
  error: "Error",
  disconnected: "Disconnected",
};

export function SourceStatusBadge({ status }: { status: SourceStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>;
}

const RUN_VARIANT: Record<SyncRun["status"], BadgeProps["variant"]> = {
  queued: "warning",
  running: "warning",
  succeeded: "success",
  partial: "warning",
  failed: "destructive",
  cancelled: "outline",
};

export function RunStatusBadge({ status }: { status: SyncRun["status"] }) {
  return <Badge variant={RUN_VARIANT[status]}>{status}</Badge>;
}

const UNITS: [number, string][] = [
  [60, "second"],
  [3600, "minute"],
  [86400, "hour"],
  [Infinity, "day"],
];
const DIVISORS = [1, 60, 3600, 86400];

/** "10 minutes ago" / "in 2 hours" / "never". */
export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "never";
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const abs = Math.abs(seconds);
  const index = UNITS.findIndex(([limit]) => abs < limit);
  const value = Math.max(1, Math.round(abs / DIVISORS[index]));
  const label = `${value} ${UNITS[index][1]}${value === 1 ? "" : "s"}`;
  if (abs < 45) return seconds >= 0 ? "in a moment" : "just now";
  return seconds >= 0 ? `in ${label}` : `${label} ago`;
}

export function intervalLabel(minutes: number | null): string {
  if (!minutes) return "Manual";
  if (minutes === 60) return "Hourly";
  if (minutes === 1440) return "Daily";
  if (minutes === 10080) return "Weekly";
  return `Every ${minutes} minutes`;
}

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}

/** Seconds between the source's last change and our last indexing, in words. */
export function freshnessLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 90) return `${seconds} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} days`;
}
