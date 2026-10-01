import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  clearAuthCookies,
  DISPLAY_NAME_COOKIE,
  REFRESH_COOKIE,
  setAuthCookies,
  setDisplayNameCookie,
} from "@/lib/auth/cookies";
import { decodeAccessToken, fetchDisplayName, gatewayRefresh, sessionFromClaims } from "@/lib/auth/gateway";

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
    const session = sessionFromClaims(claims);

    // The common case: a real name was already cached at login/refresh, no extra fetch needed on
    // this page load. Only hits the RAG API when the cookie is missing (an older session from
    // before this cookie existed, or it expired independently of the access token somehow) — self-
    // healing rather than a hard requirement.
    const cachedDisplayName = cookieStore.get(DISPLAY_NAME_COOKIE)?.value;
    if (cachedDisplayName) {
      session.displayName = cachedDisplayName;
    } else {
      const displayName = await fetchDisplayName(accessToken);
      if (displayName) {
        session.displayName = displayName;
        setDisplayNameCookie(cookieStore, displayName, Math.max(1, Math.floor(claims.exp - nowSeconds)));
      }
    }

    return NextResponse.json({ user: session });
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

    const session = sessionFromClaims(freshClaims);
    const displayName = await fetchDisplayName(tokens.accessToken);
    if (displayName) {
      session.displayName = displayName;
      setDisplayNameCookie(cookieStore, displayName, tokens.accessExpiresIn ?? 15 * 60);
    }

    return NextResponse.json({ user: session });
  } catch {
    clearAuthCookies(cookieStore);
    return NextResponse.json({ user: null });
  }
}
