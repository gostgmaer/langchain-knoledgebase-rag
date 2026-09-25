"use client";

import { useQuery } from "@tanstack/react-query";

/**
 * Whether anyone may sign up (IAM `auth.registration.enabled`). When false the platform
 * is invite-only: the login page hides "Create an account" and the register page only
 * works from an invitation link. Defaults to open while loading or if the lookup fails.
 */
export function useRegistrationOpen(): boolean {
  const { data } = useQuery({
    queryKey: ["auth-config"],
    queryFn: async () => {
      const res = await fetch("/api/auth/providers");
      return res.ok ? ((await res.json()) as { registrationOpen?: boolean }) : {};
    },
    staleTime: 60_000,
  });
  return data?.registrationOpen !== false;
}
