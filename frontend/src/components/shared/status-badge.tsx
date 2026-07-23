import { Badge, type BadgeProps } from "@/components/ui/badge";

const VARIANT_BY_STATUS: Record<string, BadgeProps["variant"]> = {
  READY: "success",
  ACTIVE: "success",
  SUCCEEDED: "success",
  COMPLETED: "success",
  PROCESSING: "warning",
  PENDING: "warning",
  QUEUED: "warning",
  RUNNING: "warning",
  FAILED: "destructive",
  DISABLED: "outline",
  ARCHIVED: "outline",
  DEPRECATED: "outline",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={VARIANT_BY_STATUS[status] ?? "secondary"}>{status}</Badge>;
}
