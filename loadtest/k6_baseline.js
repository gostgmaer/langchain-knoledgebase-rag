// docs/BUGS.md item 6: no load/performance testing tooling existed at all — no evidence-based
// answer to "how many concurrent users can this handle," a basic launch question. This is a real,
// runnable k6 script against this app's actual API (not a toy), covering three realistic request
// shapes at increasing cost: an unauthenticated health check, an authenticated list read, and a
// real retrieval-pipeline search (embedding + hybrid search + cross-encoder rerank — the most
// expensive path this script exercises; a full POST /chat round trip, which also pays for a real
// LLM generation, is deliberately NOT included here so running this doesn't silently rack up
// provider costs on every run — see chat_smoke.js for that, run it separately and deliberately).
//
// Usage (k6 is a standalone binary, not an npm/pip package — get it from
// https://k6.io/docs/get-started/installation/ or `docker run --rm -i grafana/k6 run - <script`):
//
//   BASE_URL=http://localhost:8088 \
//   BEARER_TOKEN=<a real access token — see README below> \
//   TENANT_ID=<that token's own tenant id> \
//   k6 run loadtest/k6_baseline.js
//
// Getting a BEARER_TOKEN/TENANT_ID pair for a local run: log in through the real IAM gateway
// (same call the frontend itself makes) and read the two fields off the response —
//
//   curl -s -X POST $AUTH_GATEWAY_URL/api/auth/login -H "Content-Type: application/json" \
//     -H "Origin: http://localhost:3000" -d '{"email":"<email>","password":"<password>"}'
//   # -> data.accessToken is BEARER_TOKEN; decode its JWT payload for tenantId (TENANT_ID)
//
// Access tokens are short-lived (15 min in this dev environment) — get a fresh one if a run
// starts failing every request with 401.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8088";
const BEARER_TOKEN = __ENV.BEARER_TOKEN || "";
const TENANT_ID = __ENV.TENANT_ID || "";

const AUTH_HEADERS = {
  "Content-Type": "application/json",
  Authorization: `Bearer ${BEARER_TOKEN}`,
  "X-Tenant-ID": TENANT_ID,
};

// A deliberately modest baseline, not a stress test — 15 concurrent users is a realistic upper
// bound for most B2B admin/RAG tools, not a number picked to make the system look good. Re-run
// with a higher `target` once this passes cleanly to find where it actually breaks.
export const options = {
  stages: [
    { duration: "20s", target: 15 }, // ramp up
    { duration: "1m", target: 15 }, // hold
    { duration: "15s", target: 0 }, // ramp down
  ],
  thresholds: {
    // Real SLOs, not aspirational numbers — a health check failing or being slow under load is
    // a genuine red flag; search is allowed more headroom since it's a real embedding+rerank call.
    "http_req_duration{endpoint:health}": ["p(95)<500"],
    "http_req_duration{endpoint:documents_list}": ["p(95)<2000"],
    "http_req_duration{endpoint:search}": ["p(95)<5000"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/api/v1/health`, { tags: { endpoint: "health" } });
  check(health, { "health: status 200": (r) => r.status === 200 });

  if (BEARER_TOKEN && TENANT_ID) {
    const docs = http.get(`${BASE_URL}/api/v1/documents?limit=20`, {
      headers: AUTH_HEADERS,
      tags: { endpoint: "documents_list" },
    });
    check(docs, { "documents: status 200": (r) => r.status === 200 });

    const search = http.post(
      `${BASE_URL}/api/v1/search`,
      JSON.stringify({ query: "what is the vacation policy", limit: 5 }),
      { headers: AUTH_HEADERS, tags: { endpoint: "search" } },
    );
    check(search, { "search: status 200": (r) => r.status === 200 });
  }

  sleep(1);
}
