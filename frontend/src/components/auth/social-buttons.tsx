"use client";

import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PROVIDERS = [
  { id: "google", label: "Google" },
  { id: "microsoft", label: "Microsoft" },
  { id: "facebook", label: "Facebook" },
] as const;

type Enabled = Record<(typeof PROVIDERS)[number]["id"], boolean>;

/**
 * "Continue with ..." buttons for whichever providers an admin has enabled
 * in IAM. Renders nothing (not even the divider) when none are, so a fresh
 * environment without OAuth credentials just shows the email/password form.
 *
 * Plain links, not fetches: OAuth needs a full-page navigation to the
 * provider, and the same flow both signs in a new person and — if the email
 * already has an account — links the provider to that existing account
 * (IAM's processSocialProfile), which is exactly the wording used here.
 */
export function SocialButtons({ verb = "Continue" }: { verb?: string }) {
  const [enabled, setEnabled] = useState<Enabled | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/providers")
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => !cancelled && setEnabled(json))
      .catch(() => !cancelled && setEnabled(null));
    return () => {
      cancelled = true;
    };
  }, []);

  // Always show every provider so the options are discoverable. One an admin
  // has not enabled in IAM yet is shown disabled (rather than hidden, or a
  // live button that would only bounce back with an error).
  const anyUnavailable = enabled !== null && PROVIDERS.some((p) => !enabled[p.id]);

  return (
    <div className="grid gap-3">
      <div className="flex items-center gap-3 text-xs text-neutral-500">
        <span className="h-px flex-1 bg-neutral-200 dark:bg-neutral-800" />
        or
        <span className="h-px flex-1 bg-neutral-200 dark:bg-neutral-800" />
      </div>
      {PROVIDERS.map((p) =>
        enabled?.[p.id] ? (
          <a
            key={p.id}
            href={`/api/auth/social/${p.id}/start`}
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "w-full")}
          >
            {verb} with {p.label}
          </a>
        ) : (
          <span
            key={p.id}
            role="link"
            aria-disabled="true"
            title={enabled === null ? "Checking availability..." : `${p.label} sign-in is not set up yet`}
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "w-full cursor-not-allowed opacity-50")}
          >
            {verb} with {p.label}
          </span>
        ),
      )}
      {anyUnavailable && (
        <p className="text-center text-xs text-neutral-500">
          Greyed-out options are not set up yet. An administrator can enable them in IAM settings.
        </p>
      )}
    </div>
  );
}
