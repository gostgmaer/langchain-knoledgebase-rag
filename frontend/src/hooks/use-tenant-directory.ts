"use client";

import { useQuery } from "@tanstack/react-query";

export interface DirectoryTenant {
  internalId: string;
  publicId: string;
  name: string;
  slug: string;
  isActive: boolean;
  isDefault: boolean;
  createdAt: string;
}

async function json<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error ?? "Request failed.");
  return body as T;
}

// The IAM gateway wraps payloads as { success, data }, and the BFF wraps that again as { data }.
function asTenants(value: unknown): DirectoryTenant[] {
  const inner = (value as { data?: unknown })?.data ?? value;
  if (Array.isArray(inner)) return inner as DirectoryTenant[];
  const nested = (inner as { data?: unknown })?.data;
  return Array.isArray(nested) ? (nested as DirectoryTenant[]) : [];
}

/**
 * Every real tenant on the platform, by name — the one real directory IAM's `GET /tenants`
 * exposes (`tenant:read_all`, super_admin today). Used anywhere an admin needs to pick a tenant:
 * the Tenants page, Feature Flags' scope picker, and the topbar's cross-tenant switcher. Nobody
 * should ever have to type or read a raw tenant UUID to use this app (docs/BUGS.md item 34).
 */
export function useTenantDirectory() {
  return useQuery({
    queryKey: ["tenant-directory"],
    queryFn: async () => asTenants(await json<unknown>("/api/iam/tenants?page=1&limit=100")),
    retry: false,
    staleTime: 60_000,
  });
}
