import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { ACCESS_COOKIE } from "@/lib/auth/cookies";

// Presence-only check — no signature verification here (this app doesn't
// hold the gateway's public key/JWKS config). Real enforcement of "is this
// token still valid" happens in GET /api/auth/session (which can refresh
// or reject it) and in AppShell's client-side role guard; this just stops
// an unauthenticated request from rendering a protected page's shell at
// all, rather than flashing it before client JS redirects.
// Reachable while signed out: the login page, and the pages/handlers an
// invite email or a social-login redirect lands on before any cookie exists.
const PUBLIC_PATHS = new Set(["/", "/register", "/accept-invite", "/auth/callback"]);

export function proxy(request: NextRequest) {
  if (PUBLIC_PATHS.has(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  const isLoggedIn = request.cookies.has(ACCESS_COOKIE);

  if (!isLoggedIn) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
