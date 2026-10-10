import { NextResponse } from "next/server";

// Used by the production Docker image's HEALTHCHECK (frontend/Dockerfile) and by the load
// balancer in front of it. Lives under /api/ on purpose: proxy.ts's matcher already excludes
// every /api/* path from the auth gate, so this is reachable with no session cookie — exactly
// what an external health check needs — without adding it to PUBLIC_PATHS.
export function GET() {
  return NextResponse.json({ status: "ok" });
}
