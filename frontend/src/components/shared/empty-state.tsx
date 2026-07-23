import { type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-neutral-200 py-16 text-center dark:border-neutral-800">
      <Icon className="mb-3 h-8 w-8 text-neutral-300 dark:text-neutral-700" />
      <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-xs text-neutral-500 dark:text-neutral-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
