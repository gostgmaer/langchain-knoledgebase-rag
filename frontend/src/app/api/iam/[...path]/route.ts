import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { GatewayError, gatewayJson } from "@/lib/auth/gateway";

/**
 * Narrow, cookie-authenticated passthrough to the IAM gateway for the team /
 * invitation screens. The browser can't call the gateway directly (the access
 * token lives in an httpOnly cookie), so this attaches it server-side.
 *
 * Deliberately an explicit allowlist of method + path shape — not a generic
 * proxy — so this app can never be used to reach an IAM route it doesn't have
 * a screen for. IAM itself still enforces permissions on every call (invite
 * needs tenant:user:add and a verified email; accept only works for the
 * invite's own email), this just limits what's reachable at all.
 */
const ID = "[A-Za-z0-9_-]+";
const ROUTES: { method: string; pattern: RegExp }[] = [
  { method: "GET", pattern: /^rbac\/roles$/ },
  { method: "POST", pattern: new RegExp(`^tenants/${ID}/invite$`) },
  { method: "GET", pattern: new RegExp(`^tenants/${ID}/invitations$`) },
  { method: "DELETE", pattern: new RegExp(`^tenants/${ID}/invitations/${ID}$`) },
  { method: "POST", pattern: /^tenants\/invitations\/accept$/ },
];

async function handle(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const joined = path.join("/");

  if (!ROUTES.some((r) => r.method === request.method && r.pattern.test(joined))) {
    return NextResponse.json({ error: "Not found." }, { status: 404 });
  }

  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  }

  const url = new URL(request.url);
  const body = request.method === "GET" || request.method === "DELETE" ? undefined : await request.json().catch(() => ({}));

  try {
    const data = await gatewayJson(
      `/api/${joined}${url.search}`,
      { method: request.method, body, accessToken },
      url.origin,
    );
    return NextResponse.json({ data });
  } catch (error) {
    const status = error instanceof GatewayError ? error.status : 502;
    const message = error instanceof GatewayError ? error.message : "Request failed.";
    return NextResponse.json({ error: message }, { status });
  }
}

export { handle as GET, handle as POST, handle as DELETE };
