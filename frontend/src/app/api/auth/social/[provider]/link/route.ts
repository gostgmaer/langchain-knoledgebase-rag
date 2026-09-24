import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE } from "@/lib/auth/cookies";
import { GATEWAY_PUBLIC_URL, GatewayError, gatewayJson } from "@/lib/auth/gateway";

const ALLOWED = new Set(["google", "microsoft", "facebook"]);

/**
 * "Connect <provider>" for a signed-in user. IAM issues a short-lived,
 * single-use link token bound to this user; the OAuth round trip then attaches
 * the provider to *this* account (rather than signing in as whoever the
 * provider says) - which is the only route that can link a provider whose
 * email isn't trusted for automatic linking (e.g. multi-tenant Microsoft).
 * IAM finishes by redirecting back to /dashboard/settings.
 */
export async function GET(request: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  const origin = new URL(request.url).origin;

  if (!ALLOWED.has(provider)) {
    return NextResponse.json({ error: "Unsupported provider." }, { status: 404 });
  }

  const accessToken = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!accessToken) return NextResponse.redirect(`${origin}/`, 302);

  try {
    const { linkToken } = await gatewayJson<{ linkToken: string }>(
      "/api/auth/social/link/start",
      { method: "POST", body: { provider }, accessToken },
      origin,
    );
    const target = new URL(`${GATEWAY_PUBLIC_URL}/api/auth/social/${provider}/start`);
    target.searchParams.set("link_token", linkToken);
    return NextResponse.redirect(target.toString(), 302);
  } catch (error) {
    const message = error instanceof GatewayError ? error.message : "Could not start linking.";
    return NextResponse.redirect(`${origin}/dashboard/settings?link_error=${encodeURIComponent(message)}`, 302);
  }
}
