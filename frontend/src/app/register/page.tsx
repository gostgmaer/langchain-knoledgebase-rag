"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { SocialButtons } from "@/components/auth/social-buttons";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PENDING_INVITE_KEY } from "@/lib/invite";

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  // Invite emails link here as /register?inviteToken=... for people who
  // don't have an account yet.
  const inviteToken = useSearchParams().get("inviteToken") ?? "";
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ firstName, lastName, email, password, inviteToken }),
      });
      const json = await res.json().catch(() => null);

      if (!res.ok) throw new Error(json?.error ?? "Registration failed.");

      // IAM consumes an invite token during registration itself (the new user
      // is placed in the inviting workspace right then), so there is nothing
      // left to "resume" after sign-in. Drop any pending marker the
      // /accept-invite page left behind, or the login page would bounce them
      // back to it with an already-used token.
      try {
        window.sessionStorage.removeItem(PENDING_INVITE_KEY);
      } catch {
        // storage unavailable — nothing to clear
      }

      if (json?.authenticated) {
        // Full navigation, not router.push: the session context only hydrates
        // on load, and the new cookies need to be picked up from scratch.
        window.location.assign("/");
        return;
      }

      setNotice(json?.message ?? "Account created. Check your email to verify your address, then sign in.");
      setSubmitting(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
            {inviteToken
              ? "You've been invited to join a workspace. Use the email address the invitation was sent to."
              : "Sign up with email, or continue with a provider below."}
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <Card>
            <CardContent className="grid gap-4 pt-5">
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="firstName">First name</Label>
                  <Input id="firstName" autoComplete="given-name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="lastName">Last name</Label>
                  <Input id="lastName" autoComplete="family-name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
                </div>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                />
                <p className="text-xs text-neutral-500">
                  At least 8 characters with upper and lower case, a number, and one of @$!%*?&.
                </p>
              </div>
              {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
              {notice && <p className="text-sm text-green-700 dark:text-green-400">{notice}</p>}
              <Button type="submit" size="lg" loading={submitting}>
                Create account
              </Button>
              <SocialButtons verb="Sign up" />
            </CardContent>
          </Card>
        </form>

        <p className="mt-4 text-center text-sm text-neutral-500 dark:text-neutral-400">
          Already have an account?{" "}
          <Link href="/" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
