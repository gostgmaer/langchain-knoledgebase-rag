"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PENDING_INVITE_KEY } from "@/lib/invite";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

type Result = { ok: true } | { ok: false; message: string };

export default function AcceptInvitePage() {
  // useSearchParams needs a Suspense boundary so the page can still prerender.
  return (
    <Suspense>
      <AcceptInvite />
    </Suspense>
  );
}

function AcceptInvite() {
  const token = useSearchParams().get("inviteToken");
  const { session, isLoading } = useSession();
  // Only ever set from the accept request's own completion — everything else
  // on screen is derived from token/session, not copied into state.
  const [result, setResult] = useState<Result | null>(null);
  // Strict-mode/dev double-invocation guard: an invite token is single-use,
  // so a second POST would report the invite as already consumed.
  const attempted = useRef(false);

  useEffect(() => {
    if (isLoading || !token) return;

    if (!session) {
      // Not signed in yet: remember the invite so the login page (password or
      // social) forwards back here afterwards.
      try {
        window.sessionStorage.setItem(PENDING_INVITE_KEY, token);
      } catch {
        // storage unavailable — they can re-open the emailed link after signing in
      }
      return;
    }

    if (attempted.current) return;
    attempted.current = true;

    fetch("/api/iam/tenants/invitations/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then(async (res) => {
        const json = await res.json().catch(() => null);
        if (!res.ok) throw new Error(json?.error ?? "Could not accept this invitation.");
        try {
          window.sessionStorage.removeItem(PENDING_INVITE_KEY);
        } catch {
          // ignore
        }
        // The session's tenant is baked into the access token, so it can't
        // see the new membership until a fresh sign-in mints a new one.
        await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
        setResult({ ok: true });
      })
      .catch((err) => {
        setResult({ ok: false, message: err instanceof Error ? err.message : "Could not accept this invitation." });
      });
  }, [isLoading, session, token]);

  const view = !token
    ? "error"
    : isLoading
      ? "checking"
      : !session
        ? "needs-signin"
        : result === null
          ? "accepting"
          : result.ok
            ? "accepted"
            : "error";

  const errorMessage = !token
    ? "This invitation link is missing its token."
    : result && !result.ok
      ? result.message
      : null;

  const registerHref = token ? `/register?inviteToken=${encodeURIComponent(token)}` : "/register";

  return (
    <div className="flex min-h-screen flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <h1 className="mb-6 text-center text-2xl font-semibold tracking-tight">Workspace invitation</h1>
        <Card>
          <CardContent className="grid gap-4 pt-5 text-sm">
            {view === "checking" && <p className="text-neutral-500">Checking your invitation…</p>}
            {view === "accepting" && <p className="text-neutral-500">Accepting your invitation…</p>}

            {view === "needs-signin" && (
              <>
                <p>
                  Sign in — or create an account — with the email address this invitation was sent to,
                  and you&apos;ll be added to the workspace.
                </p>
                <Link href="/" className={cn(buttonVariants({ size: "lg" }))}>
                  Sign in
                </Link>
                <Link href={registerHref} className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
                  Create an account
                </Link>
              </>
            )}

            {view === "accepted" && (
              <>
                <p className="text-green-700 dark:text-green-400">
                  You&apos;ve joined the workspace. For security we&apos;ve signed you out - sign in again
                  to enter it.
                </p>
                <Link href="/" className={cn(buttonVariants({ size: "lg" }))}>
                  Sign in
                </Link>
              </>
            )}

            {view === "error" && (
              <>
                <p className="text-red-600 dark:text-red-400">{errorMessage}</p>
                <Link href="/" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
                  Back to sign in
                </Link>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
