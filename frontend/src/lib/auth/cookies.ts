import "server-only";

import type { cookies } from "next/headers";

import type { GatewayTokens } from "@/lib/auth/gateway";

// This app's own cookies, distinct from the gateway's ea_refresh_token/
// easydev_session cookies — those are set on server-to-server responses
// this app never forwards to the browser. Same-origin, so no SameSite
// cross-site restriction applies here the way it does for the gateway.
export const ACCESS_COOKIE = "rag_access_token";
export const REFRESH_COOKIE = "rag_refresh_token";
// A real display name (RAG API's GET /auth/me — the access token's own JWT claims don't carry
// one) cached here so GET /api/auth/session's fast path (hit on every page load) doesn't have to
// fetch it again every time; set once at login/refresh, read from then on. Not sensitive — just a
// name — but httpOnly anyway for consistency with the other two and since nothing needs to read
// it client-side (components get it through the session object already).
export const DISPLAY_NAME_COOKIE = "rag_display_name";

const DEFAULT_ACCESS_MAX_AGE = 15 * 60;
const DEFAULT_REFRESH_MAX_AGE = 7 * 24 * 60 * 60;

type CookieStore = Awaited<ReturnType<typeof cookies>>;

export function setAuthCookies(cookieStore: CookieStore, tokens: GatewayTokens): void {
  const secure = process.env.NODE_ENV === "production";

  cookieStore.set(ACCESS_COOKIE, tokens.accessToken, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: tokens.accessExpiresIn ?? DEFAULT_ACCESS_MAX_AGE,
  });

  cookieStore.set(REFRESH_COOKIE, tokens.refreshToken, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/api/auth",
    maxAge: tokens.refreshExpiresIn ?? DEFAULT_REFRESH_MAX_AGE,
  });
}

export function setDisplayNameCookie(cookieStore: CookieStore, displayName: string, maxAge: number): void {
  cookieStore.set(DISPLAY_NAME_COOKIE, displayName, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge,
  });
}

export function clearAuthCookies(cookieStore: CookieStore): void {
  cookieStore.delete({ name: ACCESS_COOKIE, path: "/" });
  cookieStore.delete({ name: REFRESH_COOKIE, path: "/api/auth" });
  cookieStore.delete({ name: DISPLAY_NAME_COOKIE, path: "/" });
}
