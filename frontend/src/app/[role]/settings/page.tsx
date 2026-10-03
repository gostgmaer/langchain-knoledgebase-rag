"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const PROVIDERS = [
  { id: "google", label: "Google" },
  { id: "microsoft", label: "Microsoft" },
  { id: "facebook", label: "Facebook" },
] as const;

interface SocialAccount {
  id: string;
  provider: string;
  createdAt: string;
}

interface Profile {
  email: string;
  firstName: string | null;
  lastName: string | null;
  displayName: string | null;
  phone: string | null;
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error ?? "Request failed.");
  return body as T;
}

// The IAM gateway wraps payloads as { success, data }, and the BFF wraps that
// again as { data } - accept either shape.
const unwrap = (value: unknown): unknown => {
  const inner = (value as { data?: unknown })?.data ?? value;
  const nested = (inner as { data?: unknown })?.data;
  return nested !== undefined ? nested : inner;
};

const asAccounts = (value: unknown): SocialAccount[] => {
  const inner = unwrap(value);
  return Array.isArray(inner) ? (inner as SocialAccount[]) : [];
};

const asProfile = (value: unknown): Profile => unwrap(value) as Profile;

function SettingsContent() {
  const search = useSearchParams();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const linked = search.get("linked");
  const linkError = search.get("link_error");

  const enabledQuery = useQuery({
    queryKey: ["social-enabled"],
    queryFn: () => json<Record<string, boolean>>("/api/auth/providers"),
  });
  const accountsQuery = useQuery({
    queryKey: ["social-accounts"],
    queryFn: async () => asAccounts(await json<unknown>("/api/iam/auth/social/accounts")),
  });

  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: async () => asProfile(await json<unknown>("/api/iam/profile")),
  });

  const [profileDraft, setProfileDraft] = useState({ firstName: "", lastName: "", displayName: "", phone: "" });
  useEffect(() => {
    if (!profileQuery.data) return;
    setProfileDraft({
      firstName: profileQuery.data.firstName ?? "",
      lastName: profileQuery.data.lastName ?? "",
      displayName: profileQuery.data.displayName ?? "",
      phone: profileQuery.data.phone ?? "",
    });
  }, [profileQuery.data]);

  const updateProfile = useMutation({
    mutationFn: (body: Partial<typeof profileDraft>) =>
      json("/api/iam/profile", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const [passwordDraft, setPasswordDraft] = useState({ currentPassword: "", newPassword: "", confirmPassword: "" });
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const changePassword = useMutation({
    mutationFn: (body: { currentPassword: string; newPassword: string }) =>
      json("/api/iam/auth/password/change", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      setError(null);
      setPasswordSuccess(true);
      setPasswordDraft({ currentPassword: "", newPassword: "", confirmPassword: "" });
    },
    onError: (e: Error) => {
      setPasswordSuccess(false);
      setError(e.message);
    },
  });

  const unlink = useMutation({
    mutationFn: (provider: string) => json(`/api/iam/auth/social/unlink/${provider}`, { method: "DELETE" }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["social-accounts"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const connected = new Set((accountsQuery.data ?? []).map((a) => a.provider));
  const visible = PROVIDERS.filter((p) => enabledQuery.data?.[p.id] || connected.has(p.id));

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage how you sign in." />

      {linked && (
        <p className="rounded-md border border-green-500/40 bg-green-500/10 px-3 py-2 text-sm">
          {linked} is now connected to your account.
        </p>
      )}
      {(linkError || error) && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {linkError ?? error}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>{profileQuery.data?.email}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              updateProfile.mutate(profileDraft);
            }}
          >
            <div className="grid gap-1.5">
              <Label>First name</Label>
              <Input
                value={profileDraft.firstName}
                onChange={(e) => setProfileDraft((d) => ({ ...d, firstName: e.target.value }))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Last name</Label>
              <Input
                value={profileDraft.lastName}
                onChange={(e) => setProfileDraft((d) => ({ ...d, lastName: e.target.value }))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Display name</Label>
              <Input
                value={profileDraft.displayName}
                onChange={(e) => setProfileDraft((d) => ({ ...d, displayName: e.target.value }))}
                placeholder="Shown instead of your email where there's room"
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Phone</Label>
              <Input
                value={profileDraft.phone}
                onChange={(e) => setProfileDraft((d) => ({ ...d, phone: e.target.value }))}
              />
            </div>
            <Button type="submit" loading={updateProfile.isPending} className="justify-self-start sm:col-span-2">
              Save profile
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>Change the password you sign in with.</CardDescription>
        </CardHeader>
        <CardContent>
          {passwordSuccess && (
            <p className="mb-4 rounded-md border border-green-500/40 bg-green-500/10 px-3 py-2 text-sm">
              Password changed.
            </p>
          )}
          <form
            className="grid max-w-sm gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              setPasswordSuccess(false);
              if (passwordDraft.newPassword !== passwordDraft.confirmPassword) {
                setError("New password and confirmation don't match.");
                return;
              }
              changePassword.mutate({
                currentPassword: passwordDraft.currentPassword,
                newPassword: passwordDraft.newPassword,
              });
            }}
          >
            <div className="grid gap-1.5">
              <Label>Current password</Label>
              <Input
                type="password"
                value={passwordDraft.currentPassword}
                onChange={(e) => setPasswordDraft((d) => ({ ...d, currentPassword: e.target.value }))}
                required
              />
            </div>
            <div className="grid gap-1.5">
              <Label>New password</Label>
              <Input
                type="password"
                value={passwordDraft.newPassword}
                onChange={(e) => setPasswordDraft((d) => ({ ...d, newPassword: e.target.value }))}
                minLength={8}
                required
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Confirm new password</Label>
              <Input
                type="password"
                value={passwordDraft.confirmPassword}
                onChange={(e) => setPasswordDraft((d) => ({ ...d, confirmPassword: e.target.value }))}
                minLength={8}
                required
              />
            </div>
            <Button type="submit" loading={changePassword.isPending} className="justify-self-start">
              Change password
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connected accounts</CardTitle>
          <CardDescription>
            Connect a provider to sign in with it as well as your password. Signing in with a provider that
            confirms your email connects it automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {visible.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No social sign-in providers are enabled by your administrator.
            </p>
          )}
          {visible.map((p) => {
            const isConnected = connected.has(p.id);
            return (
              <div key={p.id} className="flex items-center justify-between rounded-md border p-3">
                <div className="flex items-center gap-3">
                  <span className="font-medium">{p.label}</span>
                  <Badge variant={isConnected ? "default" : "secondary"}>
                    {isConnected ? "Connected" : "Not connected"}
                  </Badge>
                </div>
                {isConnected ? (
                  <Button variant="outline" size="sm" disabled={unlink.isPending} onClick={() => unlink.mutate(p.id)}>
                    Disconnect
                  </Button>
                ) : (
                  // Full-page navigation: OAuth can't run inside a fetch.
                  <a
                    href={`/api/auth/social/${p.id}/link`}
                    className={cn(buttonVariants({ size: "sm" }))}
                  >
                    Connect
                  </a>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsContent />
    </Suspense>
  );
}
