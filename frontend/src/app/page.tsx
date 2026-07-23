"use client";

import { Boxes, ShieldCheck, UserCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DEFAULT_TENANT_ID,
  DEFAULT_USER_ID,
  ROLE_HOME,
  ROLE_LABELS,
  type Role,
  useSession,
} from "@/lib/session";
import { cn } from "@/lib/utils";

const ROLE_CARDS: { role: Role; icon: typeof ShieldCheck; blurb: string }[] = [
  {
    role: "admin",
    icon: ShieldCheck,
    blurb: "Cross-tenant operator view. Browse any tenant by ID, manage global model profiles.",
  },
  {
    role: "tenant_admin",
    icon: Boxes,
    blurb: "Manage one tenant's agents, prompts, tools, knowledge bases, and review feedback.",
  },
  {
    role: "customer",
    icon: UserCircle,
    blurb: "Chat only, with conversation history to resume — the end-user experience.",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const { session, login, isLoading } = useSession();
  const [role, setRole] = useState<Role>("customer");
  const [tenantId, setTenantId] = useState(DEFAULT_TENANT_ID);
  const [userId, setUserId] = useState(DEFAULT_USER_ID);
  const [displayName, setDisplayName] = useState("");

  useEffect(() => {
    if (!isLoading && session) {
      router.replace(ROLE_HOME[session.role]);
    }
  }, [isLoading, session, router]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    login({
      role,
      tenantId: tenantId.trim(),
      userId: userId.trim(),
      displayName: displayName.trim() || ROLE_LABELS[role],
    });
    router.push(ROLE_HOME[role]);
  }

  return (
    <div className="flex min-h-screen flex-1 items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">RAG Platform Console</h1>
          <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
            This picks a role and identity, then sends it as{" "}
            <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs dark:bg-neutral-800">
              X-Tenant-ID
            </code>{" "}
            /{" "}
            <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs dark:bg-neutral-800">
              X-User-ID
            </code>{" "}
            on every request — the exact fallback the backend itself already uses when no real
            token is presented. Not real authentication; there is no password.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            {ROLE_CARDS.map(({ role: r, icon: Icon, blurb }) => (
              <button
                type="button"
                key={r}
                onClick={() => setRole(r)}
                className={cn(
                  "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors",
                  role === r
                    ? "border-neutral-900 bg-neutral-900/5 dark:border-neutral-100 dark:bg-neutral-100/10"
                    : "border-neutral-200 hover:border-neutral-300 dark:border-neutral-800 dark:hover:border-neutral-700",
                )}
              >
                <Icon className="h-5 w-5" />
                <span className="text-sm font-semibold">{ROLE_LABELS[r]}</span>
                <span className="text-xs text-neutral-500 dark:text-neutral-400">{blurb}</span>
              </button>
            ))}
          </div>

          <Card>
            <CardContent className="grid gap-4 pt-5">
              <div className="grid gap-1.5">
                <Label htmlFor="displayName">Display name</Label>
                <Input
                  id="displayName"
                  placeholder={ROLE_LABELS[role]}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="tenantId">
                  {role === "admin" ? "Tenant to browse first" : "Tenant ID"}
                </Label>
                <Input
                  id="tenantId"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="userId">User ID</Label>
                <Input id="userId" value={userId} onChange={(e) => setUserId(e.target.value)} required />
              </div>
              <Button type="submit" size="lg">
                Continue as {ROLE_LABELS[role]}
              </Button>
            </CardContent>
          </Card>
        </form>
      </div>
    </div>
  );
}
