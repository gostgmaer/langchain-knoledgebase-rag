import "server-only";

import { decodeJwt } from "jose";

import type { Role, Session } from "@/lib/session";

// Server-only client for the auth gateway at
// c:\Users\kisho\WorkSpace\Backend\web-agency-backend-api — never called
// from the browser. This app's Next.js route handlers
// (app/api/auth/*/route.ts) are the only callers, which is what makes the
// gateway's SameSite=Strict cookies a non-issue: they're set on server-to-
// server responses this app never forwards, and we mint our own
// same-origin cookies instead (see lib/auth/cookies.ts).
const GATEWAY_URL = process.env.AUTH_GATEWAY_URL ?? "http://localhost:3301";

export class GatewayError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "GatewayError";
    this.status = status;
  }
}

export interface GatewayTokens {
  accessToken: string;
  refreshToken: string;
  accessExpiresIn?: number;
  refreshExpiresIn?: number;
}

// The gateway's CSRF-origin guard (web-agency-backend-api/app.js) rejects
// any state-changing request with neither an Origin nor a Referer header.
// Node's server-side fetch sends neither by default (only browsers do),
// so every call here must pass this app's own origin explicitly — it's
// the honest value anyway, since we're a trusted BFF acting on behalf of
// whichever origin the browser actually loaded this app from.
async function gatewayFetch(path: string, init: RequestInit, origin: string): Promise<GatewayTokens> {
  let response: Response;
  try {
    response = await fetch(`${GATEWAY_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", Origin: origin, ...init.headers },
    });
  } catch {
    throw new GatewayError(
      "Could not reach the auth gateway — check AUTH_GATEWAY_URL is pointed at a running instance.",
      502,
    );
  }

  const json = await response.json().catch(() => null);

  if (!response.ok) {
    throw new GatewayError(json?.message ?? "Authentication failed.", response.status);
  }

  // IAM wraps every response in an envelope: {success, data: {accessToken,
  // refreshToken, ...}, message, ...} — confirmed against a real login
  // response, not just the gateway's own source (which reads through the
  // same envelope before re-serving it here unchanged).
  const data = json?.data;

  if (!data?.accessToken || !data?.refreshToken) {
    throw new GatewayError("Gateway response did not include tokens.", 502);
  }

  return {
    accessToken: data.accessToken,
    refreshToken: data.refreshToken,
    accessExpiresIn: data.accessExpiresIn,
    refreshExpiresIn: data.refreshExpiresIn,
  };
}

export function gatewayLogin(email: string, password: string, origin: string): Promise<GatewayTokens> {
  return gatewayFetch(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
    origin,
  );
}

export function gatewayRefresh(refreshToken: string, origin: string): Promise<GatewayTokens> {
  return gatewayFetch(
    "/api/auth/refresh",
    { method: "POST", body: JSON.stringify({ refreshToken }) },
    origin,
  );
}

export async function gatewayLogout(
  refreshToken: string | undefined,
  accessToken: string | undefined,
  origin: string,
): Promise<void> {
  try {
    await fetch(`${GATEWAY_URL}/api/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: origin,
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ refreshToken }),
    });
  } catch {
    // Best-effort — our own cookies are cleared by the caller regardless,
    // so a gateway/IAM outage shouldn't block the user from logging out.
  }
}

export interface AccessTokenClaims {
  userId: string;
  email: string;
  iamRole: string;
  roles: string[];
  tenantId: string;
  tenantSlug?: string;
  sessionId?: string;
  exp: number;
}

/**
 * Reads claims off the access token without verifying its signature. Safe
 * here specifically because this token only ever reaches our code two
 * ways: fresh from a direct HTTPS call to the gateway (trusted transport),
 * or out of our own httpOnly cookie (never readable/writable by browser
 * JS, so the trust boundary is "did our server set this cookie", not the
 * JWT signature). If this token is ever accepted from anywhere else —
 * a client-supplied header, for instance — it must be verified for real
 * against the gateway's JWKS first.
 */
export function decodeAccessToken(token: string): AccessTokenClaims {
  const claims = decodeJwt(token);
  const roles = (claims.roles as string[] | undefined) ?? [];
  const role = (claims.role as string | undefined) ?? roles[0] ?? "customer";

  return {
    userId: String(claims.sub),
    email: String(claims.email ?? ""),
    iamRole: role,
    roles,
    tenantId: String(claims.tenantId ?? ""),
    tenantSlug: claims.tenantSlug as string | undefined,
    sessionId: claims.sessionId as string | undefined,
    exp: claims.exp ?? 0,
  };
}

/**
 * IAM's role vocabulary (super_admin/tenant_admin/admin/...) doesn't line
 * up 1:1 with this app's three-tier nav model — collapse it explicitly
 * rather than assume a naming coincidence:
 *  - super_admin -> admin        (cross-tenant operator)
 *  - tenant_admin, admin -> tenant_admin  (elevated within one tenant)
 *  - anything else -> customer   (end user, chat-only)
 */
export function mapIamRoleToAppRole(iamRole: string): Role {
  if (iamRole === "super_admin") return "admin";
  if (iamRole === "tenant_admin" || iamRole === "admin") return "tenant_admin";
  return "customer";
}

export function sessionFromClaims(claims: AccessTokenClaims): Session {
  return {
    role: mapIamRoleToAppRole(claims.iamRole),
    userId: claims.userId,
    tenantId: claims.tenantId,
    displayName: claims.email,
  };
}
