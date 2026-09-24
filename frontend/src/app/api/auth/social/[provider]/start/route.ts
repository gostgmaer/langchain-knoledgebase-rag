import { NextResponse } from "next/server";

import { GATEWAY_PUBLIC_URL } from "@/lib/auth/gateway";

const ALLOWED = new Set(["google", "microsoft", "facebook"]);

// Allowlisted rather than interpolating whatever the URL says, so this can
// never be turned into an open redirect to an arbitrary gateway path.
export async function GET(_request: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;

  if (!ALLOWED.has(provider)) {
    return NextResponse.json({ error: "Unsupported sign-in provider." }, { status: 404 });
  }

  return NextResponse.redirect(`${GATEWAY_PUBLIC_URL}/api/auth/social/${provider}/start`, 302);
}
