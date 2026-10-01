// A deliberately tiny, single-request smoke test for the full chat round trip (embedding +
// retrieval + rerank + a real LLM generation) — kept separate from k6_baseline.js so a routine
// load-test run never silently racks up real LLM provider costs. Run this by hand, occasionally,
// to see end-to-end chat latency — not on every CI run.
//
// Usage: same BASE_URL/BEARER_TOKEN/TENANT_ID env vars as k6_baseline.js (see its header).
//   k6 run --vus 1 --iterations 1 loadtest/k6_chat_smoke.js

import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8088";
const BEARER_TOKEN = __ENV.BEARER_TOKEN || "";
const TENANT_ID = __ENV.TENANT_ID || "";

export default function () {
  if (!BEARER_TOKEN || !TENANT_ID) {
    throw new Error("BEARER_TOKEN and TENANT_ID are required — see k6_baseline.js's header for how to get them.");
  }

  const res = http.post(
    `${BASE_URL}/api/v1/chat`,
    JSON.stringify({ message: "What documents are in the knowledge base?" }),
    {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${BEARER_TOKEN}`,
        "X-Tenant-ID": TENANT_ID,
      },
      timeout: "60s",
    },
  );

  check(res, { "chat: status 200": (r) => r.status === 200 });
  console.log(`chat round trip: ${res.timings.duration.toFixed(0)}ms, status ${res.status}`);
}
