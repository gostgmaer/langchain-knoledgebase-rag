import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE, setAuthCookies } from "@/lib/auth/cookies";
import {
  decodeAccessToken,
  GatewayError,
  gatewayJson,
  sessionFromClaims,
  tokensFromData,
} from "@/lib/auth/gateway";

/**
 * Switch the signed-in user into another workspace they already belong to. The
 * workspace is baked into the access token, so switching means IAM issues a new
 * session for the target tenant (and revokes the old one); the fresh tokens are
 * moved straight into the httpOnly cookies and never reach client JS.
 * IAM refuses a tenant the caller is not a member of.
 */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const tenantId = typeof body?.tenantId === "string" ? body.tenantId.trim() : "";
  if (!tenantId) {
    return NextResponse.json({ error: "A workspace is required." }, { status: 400 });
  }

  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) {
    return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  }

  try {
    const data = await gatewayJson("/api/tenants/switch", { method: "POST", body: { tenantId }, accessToken }, new URL(request.url).origin);
    const tokens = tokensFromData(data);
    if (!tokens) {
      return NextResponse.json({ error: "The workspace switch did not return a session." }, { status: 502 });
    }

    setAuthCookies(cookieStore, tokens);
    return NextResponse.json({ user: sessionFromClaims(decodeAccessToken(tokens.accessToken)) });
  } catch (error) {
    const status = error instanceof GatewayError ? error.status : 502;
    const message = error instanceof GatewayError ? error.message : "Could not switch workspace.";
    return NextResponse.json({ error: message }, { status });
  }
}
