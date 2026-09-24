import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { setAuthCookies } from "@/lib/auth/cookies";
import { decodeAccessToken } from "@/lib/auth/gateway";

/**
 * Landing point for IAM's server-side social-login redirect
 * (multi-tannet-auth-services: handleCodeOAuthCallback ->
 * `${FRONTEND_URL}/auth/callback?access_token=...&refresh_token=...`, or
 * `?error=...`). A route handler rather than a page on purpose: the tokens
 * are moved straight into httpOnly cookies and the response is a redirect,
 * so they never reach client JS and never linger in the address bar or
 * browser history as a rendered page.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const error = url.searchParams.get("error");
  const accessToken = url.searchParams.get("access_token");
  const refreshToken = url.searchParams.get("refresh_token");

  const fail = (message: string) => {
    const target = new URL("/", url.origin);
    target.searchParams.set("error", message);
    return NextResponse.redirect(target, 303);
  };

  if (error) return fail(error);
  if (!accessToken || !refreshToken) return fail("Social sign-in did not complete. Please try again.");

  try {
    decodeAccessToken(accessToken);
  } catch {
    return fail("Social sign-in returned an unreadable token. Please try again.");
  }

  const cookieStore = await cookies();
  setAuthCookies(cookieStore, { accessToken, refreshToken });

  // "/" is the login page, which sends an already-signed-in session on to
  // its role home — one place owns that mapping instead of duplicating it.
  return NextResponse.redirect(new URL("/", url.origin), 303);
}
