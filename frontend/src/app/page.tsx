"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { SocialButtons } from "@/components/auth/social-buttons";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRegistrationOpen } from "@/lib/auth/use-registration-open";
import { PENDING_INVITE_KEY } from "@/lib/invite";
import { ROLE_HOME, useSession } from "@/lib/session";

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary so the page can still prerender.
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const registrationOpen = useRegistrationOpen();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, login, isLoading } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // A failed social sign-in lands back here as /?error=... (see
  // app/auth/callback/route.ts); a form submission's own error wins.
  const redirectError = searchParams.get("error");

  useEffect(() => {
    if (isLoading || !session) return;

    // Someone who opened an invite link before signing in is sent back to
    // finish accepting it, rather than dropped on their dashboard.
    let pendingInvite: string | null = null;
    try {
      pendingInvite = window.sessionStorage.getItem(PENDING_INVITE_KEY);
    } catch {
      // storage unavailable — fall through to the normal landing page
    }

    router.replace(
      pendingInvite
        ? `/accept-invite?inviteToken=${encodeURIComponent(pendingInvite)}`
        : ROLE_HOME[session.role],
    );
  }, [isLoading, session, router]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Read what is actually in the fields: browser autofill does not always update React
    // state, and can drop in a saved username from another app on the same host.
    const data = new FormData(e.currentTarget);
    const emailValue = String(data.get("email") ?? email).trim();
    const passwordValue = String(data.get("password") ?? password);

    if (!emailValue || !passwordValue) {
      setError("Enter your email address and password.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) {
      setError(`"${emailValue}" is not an email address. Sign in with the email of your account, for example name@example.com.`);
      return;
    }

    setSubmitting(true);
    try {
      const user = await login(emailValue, passwordValue);
      router.push(ROLE_HOME[user.role]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">RAG Platform Console</h1>
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
            Sign in with your EasyDev account. Your role and tenant are read from your account —
            there&apos;s nothing to pick here.
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <Card>
            <CardContent className="grid gap-4 pt-5">
              <div className="grid gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {(error ?? redirectError) && (
                <p className="text-sm text-red-600 dark:text-red-400">{error ?? redirectError}</p>
              )}
              <Button type="submit" size="lg" loading={submitting}>
                Sign in
              </Button>
              <SocialButtons verb="Continue" />
            </CardContent>
          </Card>
        </form>

        <p className="mt-4 text-center text-sm text-neutral-500 dark:text-neutral-400">
          {registrationOpen ? (
            <>
              New here?{" "}
              <Link href="/register" className="font-medium text-primary hover:underline">
                Create an account
              </Link>
            </>
          ) : (
            "Sign-up is by invitation only. Use the link in your invitation email."
          )}
        </p>
      </div>
    </div>
  );
}
