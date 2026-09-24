"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error ?? "Request failed.");
  return body as T;
}

// The IAM gateway wraps payloads as { success, data }, and the BFF wraps that
// again as { data } - accept either shape.
const asAccounts = (value: unknown): SocialAccount[] => {
  const inner = (value as { data?: unknown })?.data ?? value;
  if (Array.isArray(inner)) return inner as SocialAccount[];
  const nested = (inner as { data?: unknown })?.data;
  return Array.isArray(nested) ? (nested as SocialAccount[]) : [];
};

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
