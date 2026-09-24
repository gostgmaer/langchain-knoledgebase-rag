import { NextResponse } from "next/server";

import { gatewayJson } from "@/lib/auth/gateway";

type PublicSettings = Record<string, unknown>;

/**
 * Which social providers an admin has actually switched on (IAM platform
 * settings, exposed unauthenticated by design as branding/login config).
 * The login page only renders buttons for these, so a provider that isn't
 * configured never shows a button that would just bounce back with an error.
 * Fails closed: an unreachable gateway means no social buttons, and
 * email/password sign-in is unaffected.
 */
export async function GET(request: Request) {
  try {
    const settings = await gatewayJson<PublicSettings>(
      "/api/iam/settings/public",
      {},
      new URL(request.url).origin,
    );
    const master = settings["auth.social.enabled"] === true;

    return NextResponse.json({
      google: master && settings["auth.social.google"] === true,
      microsoft: master && settings["auth.social.microsoft"] === true,
      facebook: master && settings["auth.social.facebook"] === true,
    });
  } catch {
    return NextResponse.json({ google: false, microsoft: false, facebook: false });
  }
}
