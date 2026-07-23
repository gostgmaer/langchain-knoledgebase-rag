import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE, clearAuthCookies, REFRESH_COOKIE } from "@/lib/auth/cookies";
import { gatewayLogout } from "@/lib/auth/gateway";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;

  clearAuthCookies(cookieStore);

  // Best-effort — invalidates the session at the gateway/IAM too, so the
  // refresh token can't be replayed. Our own cookies are already gone
  // either way, so a gateway outage doesn't block logging out locally.
  await gatewayLogout(refreshToken, accessToken, new URL(request.url).origin);

  return NextResponse.json({ success: true });
}
