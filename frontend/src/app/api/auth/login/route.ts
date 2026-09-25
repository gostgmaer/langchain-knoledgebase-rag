import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { setAuthCookies } from "@/lib/auth/cookies";
import { decodeAccessToken, GatewayError, gatewayLogin, sessionFromClaims } from "@/lib/auth/gateway";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const email = typeof body?.email === "string" ? body.email.trim() : "";
  const password = typeof body?.password === "string" ? body.password : "";

  if (!email || !password) {
    return NextResponse.json({ error: "Email and password are required." }, { status: 400 });
  }

  try {
    const tokens = await gatewayLogin(email, password, new URL(request.url).origin);
    const claims = decodeAccessToken(tokens.accessToken);

    const cookieStore = await cookies();
    setAuthCookies(cookieStore, tokens);

    return NextResponse.json({ user: sessionFromClaims(claims) });
  } catch (error) {
    const status = error instanceof GatewayError ? error.status : 502;
    // IAM rate-limits sign-ins per IP; its own text ("ThrottlerException: Too Many
    // Requests") is meaningless to a user, so say what to do instead.
    const message =
      status === 429
        ? "Too many sign-in attempts. Please wait a minute and try again."
        : error instanceof GatewayError
          ? error.message
          : "Login failed.";
    return NextResponse.json({ error: message }, { status });
  }
}
