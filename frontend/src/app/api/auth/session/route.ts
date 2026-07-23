import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE, clearAuthCookies, REFRESH_COOKIE, setAuthCookies } from "@/lib/auth/cookies";
import { decodeAccessToken, gatewayRefresh, sessionFromClaims } from "@/lib/auth/gateway";

// A 30s skew tolerance avoids a request landing right at expiry racing a
// clock difference between this server and the gateway/IAM.
const EXPIRY_SKEW_SECONDS = 30;

export async function GET(request: Request) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;

  if (!accessToken) {
    return NextResponse.json({ user: null });
  }

  const nowSeconds = Date.now() / 1000;
  const claims = decodeAccessToken(accessToken);

  if (claims.exp - EXPIRY_SKEW_SECONDS > nowSeconds) {
    return NextResponse.json({ user: sessionFromClaims(claims) });
  }

  // Access token expired (or about to) — use the refresh cookie to get a
  // new pair before giving up on the session, so a page reload after 15
  // minutes doesn't force a re-login while the refresh token (7 days) is
  // still good.
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    clearAuthCookies(cookieStore);
    return NextResponse.json({ user: null });
  }

  try {
    const tokens = await gatewayRefresh(refreshToken, new URL(request.url).origin);
    const freshClaims = decodeAccessToken(tokens.accessToken);
    setAuthCookies(cookieStore, tokens);
    return NextResponse.json({ user: sessionFromClaims(freshClaims) });
  } catch {
    clearAuthCookies(cookieStore);
    return NextResponse.json({ user: null });
  }
}
