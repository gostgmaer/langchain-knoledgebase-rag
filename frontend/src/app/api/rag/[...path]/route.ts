import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { ACCESS_COOKIE, clearAuthCookies, REFRESH_COOKIE, setAuthCookies } from "@/lib/auth/cookies";
import { decodeAccessToken, gatewayRefresh } from "@/lib/auth/gateway";

/**
 * Same-origin proxy to the RAG API. The IAM access token lives in an httpOnly
 * cookie the browser can't read, so this attaches it as `Authorization:
 * Bearer` server-side. The RAG API (AUTH_REQUIRED=true) derives tenant and
 * user from that verified token - the X-Tenant-ID / X-User-ID headers the
 * client still sends are ignored there, so they can't be used to spoof.
 *
 * Bodies and responses are passed through untouched, so multipart uploads and
 * the SSE chat stream work as they do when calling the API directly.
 */
const RAG_API_URL = process.env.RAG_API_URL ?? "http://127.0.0.1:8088/api/v1";
const EXPIRY_SKEW_SECONDS = 30;

// Hop-by-hop / recomputed headers that must not be copied across.
const SKIP_REQUEST_HEADERS = new Set(["host", "connection", "content-length", "cookie", "authorization"]);
const SKIP_RESPONSE_HEADERS = new Set(["content-encoding", "content-length", "transfer-encoding", "connection"]);

async function validAccessToken(request: Request): Promise<string | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (!accessToken) return null;

  try {
    if (decodeAccessToken(accessToken).exp - EXPIRY_SKEW_SECONDS > Date.now() / 1000) return accessToken;
  } catch {
    /* fall through to refresh */
  }

  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;
  try {
    const tokens = await gatewayRefresh(refreshToken, new URL(request.url).origin);
    setAuthCookies(cookieStore, tokens);
    return tokens.accessToken;
  } catch {
    clearAuthCookies(cookieStore);
    return null;
  }
}

async function handle(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;

  const token = await validAccessToken(request);
  if (!token) return NextResponse.json({ message: "Not signed in." }, { status: 401 });

  const incoming = new URL(request.url);
  const target = `${RAG_API_URL}/${path.map(encodeURIComponent).join("/")}${incoming.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!SKIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });
  headers.set("Authorization", `Bearer ${token}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
    });
  } catch {
    return NextResponse.json({ message: "Could not reach the RAG API." }, { status: 502 });
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!SKIP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
