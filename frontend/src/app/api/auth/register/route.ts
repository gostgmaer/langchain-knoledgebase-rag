import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { setAuthCookies } from "@/lib/auth/cookies";
import {
  decodeAccessToken,
  GatewayError,
  gatewayJson,
  sessionFromClaims,
  tokensFromData,
} from "@/lib/auth/gateway";

const str = (value: unknown) => (typeof value === "string" ? value.trim() : "");

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);

  const email = str(body?.email);
  const password = typeof body?.password === "string" ? body.password : "";
  const firstName = str(body?.firstName);
  const lastName = str(body?.lastName);
  const inviteToken = str(body?.inviteToken);

  if (!email || !password) {
    return NextResponse.json({ error: "Email and password are required." }, { status: 400 });
  }

  try {
    const data = await gatewayJson<Record<string, unknown>>(
      "/api/auth/register",
      {
        method: "POST",
        body: {
          email,
          password,
          ...(firstName && { firstName }),
          ...(lastName && { lastName }),
          // IAM ignores a token that doesn't match the registering email
          // rather than failing the signup (see register() in auth.service),
          // so passing it through is always safe.
          ...(inviteToken && { inviteToken }),
        },
      },
      new URL(request.url).origin,
    );

    // Depending on tenant settings IAM either signs the new user straight in
    // or requires email verification first — handle both honestly instead of
    // assuming one.
    const tokens = tokensFromData(data);
    if (tokens) {
      const cookieStore = await cookies();
      setAuthCookies(cookieStore, tokens);
      return NextResponse.json({
        authenticated: true,
        user: sessionFromClaims(decodeAccessToken(tokens.accessToken)),
      });
    }

    return NextResponse.json({
      authenticated: false,
      message:
        typeof data?.message === "string"
          ? data.message
          : "Account created. Check your email to verify your address, then sign in.",
    });
  } catch (error) {
    const status = error instanceof GatewayError ? error.status : 502;
    const message = error instanceof GatewayError ? error.message : "Registration failed.";
    return NextResponse.json({ error: message }, { status });
  }
}
