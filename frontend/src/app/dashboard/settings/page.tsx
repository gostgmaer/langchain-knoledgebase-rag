"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { ROLE_SLUG, useSession } from "@/lib/session";

/**
 * IAM's social-link flow finishes by redirecting to /dashboard/settings (a
 * path baked into IAM). This app's settings live under the role segment, so
 * forward there with the result (?linked= / ?link_error=) intact.
 */
function Forward() {
  const router = useRouter();
  const search = useSearchParams();
  const { session } = useSession();

  useEffect(() => {
    if (!session) return;
    const query = search.toString();
    router.replace(`/${ROLE_SLUG[session.role]}/settings${query ? `?${query}` : ""}`);
  }, [session, search, router]);

  return <p className="p-6 text-sm text-muted-foreground">Redirecting...</p>;
}

export default function DashboardSettingsRedirect() {
  return (
    <Suspense>
      <Forward />
    </Suspense>
  );
}
