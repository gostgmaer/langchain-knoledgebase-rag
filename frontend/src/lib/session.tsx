"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Role = "admin" | "tenant_admin" | "customer";

export interface Session {
  role: Role;
  /** Every role's own identity. For "admin" this is the platform operator's id, not a tenant customer's. */
  userId: string;
  /** The tenant every API call is scoped to. For "admin" this is whichever tenant they're currently browsing. */
  tenantId: string;
  displayName: string;
}

interface SessionContextValue {
  session: Session | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<Session>;
  logout: () => Promise<void>;
  /** Admin-only: switch which tenant is currently being browsed, without logging out. */
  setViewingTenant: (tenantId: string) => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

// Tab-scoped (not localStorage) on purpose: an admin's "browse as tenant X"
// choice is a convenience for the current browsing session, not something
// that should silently follow them into a new tab or linger for weeks.
const VIEWING_TENANT_KEY = "rag-console-viewing-tenant";

function readStoredViewingTenant(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(VIEWING_TENANT_KEY);
  } catch {
    return null;
  }
}

function writeStoredViewingTenant(tenantId: string | null): void {
  try {
    if (tenantId) window.sessionStorage.setItem(VIEWING_TENANT_KEY, tenantId);
    else window.sessionStorage.removeItem(VIEWING_TENANT_KEY);
  } catch {
    // Storage unavailable (private browsing, etc.) — override still works
    // for this render, it just won't survive a reload.
  }
}

// How often to silently re-validate the session in the background so a
// long-open tab's access token gets refreshed well before its ~15min
// default expiry, instead of only ever refreshing on next reload/nav.
const BACKGROUND_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

export function SessionProvider({ children }: { children: ReactNode }) {
  // The real session — whoever the rag_access_token cookie (httpOnly, set
  // only by app/api/auth/*/route.ts) says is logged in. Never read/written
  // directly here; this is client state hydrated from GET /api/auth/session.
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // Admin's "browse as tenant X" override, layered on top of the real
  // session for display/API-header purposes only — it does not touch the
  // auth cookies or grant any access the admin's real token doesn't
  // already have.
  const [viewingTenantId, setViewingTenantId] = useState<string | null>(readStoredViewingTenant);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/auth/session")
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setSession(data.user);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const isAuthenticated = session !== null;

  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(() => {
      fetch("/api/auth/session")
        .then((res) => res.json())
        .then((data) => setSession(data.user))
        .catch(() => {
          // A transient network hiccup shouldn't log the user out — only
          // an explicit {user: null} response (real expiry/invalidation)
          // should, and that still comes through on the next successful poll.
        });
    }, BACKGROUND_REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isAuthenticated]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error ?? "Login failed.");
    }
    setSession(data.user);
    setViewingTenantId(null);
    writeStoredViewingTenant(null);
    return data.user as Session;
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setSession(null);
    setViewingTenantId(null);
    writeStoredViewingTenant(null);
  }, []);

  const setViewingTenant = useCallback((tenantId: string) => {
    setViewingTenantId(tenantId);
    writeStoredViewingTenant(tenantId);
  }, []);

  const effectiveSession = useMemo(() => {
    if (!session) return null;
    if (session.role === "admin" && viewingTenantId) {
      return { ...session, tenantId: viewingTenantId };
    }
    return session;
  }, [session, viewingTenantId]);

  const value = useMemo(
    () => ({ session: effectiveSession, isLoading, login, logout, setViewingTenant }),
    [effectiveSession, isLoading, login, logout, setViewingTenant],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  tenant_admin: "Tenant Admin",
  customer: "Customer",
};

/** The URL segment each role lives under — app/[role]/... — one route tree shared by all three. */
export const ROLE_SLUG: Record<Role, string> = {
  admin: "admin",
  tenant_admin: "tenant-admin",
  customer: "customer",
};

export const SLUG_TO_ROLE: Record<string, Role> = {
  admin: "admin",
  "tenant-admin": "tenant_admin",
  customer: "customer",
};

export const ROLE_HOME: Record<Role, string> = {
  admin: "/admin",
  tenant_admin: "/tenant-admin",
  customer: "/customer/chat",
};
