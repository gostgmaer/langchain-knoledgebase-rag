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

// Matches packages/api/dependencies.py's DEFAULT_TENANT_ID/DEFAULT_USER_ID —
// the same fallback the backend itself uses when no headers are sent.
export const DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001";
export const DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000002";

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
  login: (session: Session) => void;
  logout: () => void;
  /** Admin-only: switch which tenant is currently being browsed, without logging out. */
  setViewingTenant: (tenantId: string) => void;
}

const STORAGE_KEY = "rag-console-session";

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setSession(JSON.parse(raw) as Session);
    } catch {
      // Corrupt/blocked storage — treat as logged out.
    } finally {
      setIsLoading(false);
    }
  }, []);

  const persist = useCallback((next: Session | null) => {
    setSession(next);
    if (next) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const login = useCallback((next: Session) => persist(next), [persist]);
  const logout = useCallback(() => persist(null), [persist]);
  const setViewingTenant = useCallback(
    (tenantId: string) => {
      setSession((prev) => {
        if (!prev) return prev;
        const next = { ...prev, tenantId };
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return next;
      });
    },
    [],
  );

  const value = useMemo(
    () => ({ session, isLoading, login, logout, setViewingTenant }),
    [session, isLoading, login, logout, setViewingTenant],
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
