import type { ApiErrorResponse, ApiResponse } from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export interface Identity {
  tenantId: string;
  userId?: string;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  formData?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Every request goes through this one function so the X-Tenant-ID/
 * X-User-ID header attachment (this app's stand-in for real auth —
 * see lib/session.tsx) and the {success, data, message} envelope
 * unwrapping only ever need to be handled in one place.
 */
export async function apiFetch<T>(
  path: string,
  identity: Identity,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "X-Tenant-ID": identity.tenantId,
  };
  if (identity.userId) headers["X-User-ID"] = identity.userId;

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    headers,
    body,
    signal: options.signal,
  });

  const json = await response.json().catch(() => null);

  if (!response.ok) {
    const err = json as ApiErrorResponse | null;
    throw new ApiError(
      err?.message ?? response.statusText ?? "Request failed",
      response.status,
      err?.details,
    );
  }

  return (json as ApiResponse<T>).data;
}

export interface StreamChatEvent {
  type: "token" | "done" | "metadata" | string;
  content?: string;
  conversation_id?: string;
  [key: string]: unknown;
}

/**
 * POST /chat with stream=true returns a real text/event-stream body,
 * but it's a POST, so the browser's EventSource (GET-only) can't be
 * used — this reads the same SSE wire format by hand off fetch's own
 * streaming body reader instead.
 */
export async function streamChat(
  payload: Record<string, unknown>,
  identity: Identity,
  onEvent: (event: StreamChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(buildUrl("/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": identity.tenantId,
      ...(identity.userId ? { "X-User-ID": identity.userId } : {}),
    },
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  });

  if (!response.ok || !response.body) {
    const json = await response.json().catch(() => null);
    throw new ApiError(
      (json as ApiErrorResponse | null)?.message ?? "Streaming request failed",
      response.status,
      json,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const raw = line.slice("data:".length).trim();
      if (!raw) continue;
      try {
        onEvent(JSON.parse(raw) as StreamChatEvent);
      } catch {
        // Malformed chunk boundary — skip rather than crash the stream.
      }
    }
  }
}
