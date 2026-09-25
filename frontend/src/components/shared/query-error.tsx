"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

function describe(error: unknown, fallback: string): string {
  const status = (error as { status?: number } | null)?.status;
  if (status === 403) return "You don't have permission to view this. Ask a workspace admin if you need access.";
  if (status === 401) return "Your session has expired. Sign in again.";
  if (status === 503) return "The service is temporarily unavailable. Try again in a moment.";
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/**
 * The one place a failed request is shown. Views used to handle only the loading
 * and empty states, so a 403/500 left a blank or stuck screen.
 */
export function QueryError({
  error,
  message = "Something went wrong loading this.",
  onRetry,
}: {
  error?: unknown;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
      <div className="flex-1">
        <p className="font-medium text-destructive">{describe(error, message)}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
