# Load testing

`docs/BUGS.md` item 6: no load/performance testing tooling existed at all. [k6](https://k6.io/) scripts against this app's real API — not a toy, not a mock server.

- **`k6_baseline.js`** — the main script. Ramps to 15 concurrent users over real `health`/`documents`/`search` traffic, with latency/error-rate thresholds as pass/fail criteria. Run this for a routine capacity check.
- **`k6_chat_smoke.js`** — a single-request smoke test for a full chat round trip (real LLM generation included). Kept separate so a routine load-test run never silently racks up provider costs — run it by hand, occasionally.

## Getting k6

k6 is a standalone Go binary, not an npm/pip package.

- Native install: https://k6.io/docs/get-started/installation/
- Or via Docker (if your network reaches Docker Hub): `docker run --rm -i grafana/k6 run - <script`

## Running

Both scripts need `BASE_URL` (the real backend API — in this dev environment, `http://localhost:8088`, not the Next.js frontend's port), `BEARER_TOKEN`, and `TENANT_ID`. Get a token the same way the frontend itself does, through the real IAM gateway:

```bash
curl -s -X POST $AUTH_GATEWAY_URL/api/auth/login -H "Content-Type: application/json" \
  -H "Origin: http://localhost:3000" -d '{"email":"<email>","password":"<password>"}'
# -> data.accessToken is BEARER_TOKEN; decode its JWT payload for tenantId (TENANT_ID)
```

Access tokens are short-lived (15 minutes in this dev environment) — get a fresh one if a run starts failing every request with `401`.

```bash
BASE_URL=http://localhost:8088 BEARER_TOKEN=... TENANT_ID=... k6 run loadtest/k6_baseline.js
```

## A real finding from the first live run (2026-10-01)

Run live against this dev stack at 15 concurrent simulated users (a modest, realistic number, not a stress test): **76.6% of requests failed — not from backend capacity, but from the rate limiter.** The expensive-route cap (default 60/min) and the general cap (default 300/min) are both keyed on `X-Tenant-ID` (`packages/api/middleware/rate_limit.py`) — **one shared budget for an entire tenant**, not per-user. Confirmed directly: a plain follow-up request right after the run returned a real `429`. (At the time of this run both caps were the env vars `RATE_LIMIT_EXPENSIVE_REQUESTS_PER_MINUTE`/`RATE_LIMIT_REQUESTS_PER_MINUTE`; docs/BUGS.md item 38 later moved them to the database — same defaults, now admin-configurable from the Platform Settings page instead of `.env`.)

This is the rate limiter correctly doing its job (`docs/BUGS.md` item 12), not a bug — but it means the real, current answer to "how many concurrent users can one tenant handle" is uncomfortably small: **60 chat/search/upload requests per minute, shared across every concurrently active user in that tenant**, before legitimate requests start getting rejected. A tenant with as few as 10 people each sending one message a minute would already be at that ceiling. Worth a deliberate decision before onboarding a tenant with many concurrent active users — either raising the expensive-route limit on the Platform Settings page for production, or a documented per-tenant concurrency expectation — not something to leave undiscovered until a real customer hits it.

What this run did *not* yet measure: real backend/DB capacity once the rate limiter isn't the first thing to break. A follow-up run with the expensive-route limit raised or temporarily disabled (Platform Settings page, takes effect within ~30s, no restart) would find the *next* real ceiling — not done here, since changing that in a live environment is a deliberate operational decision, not something to flip silently while establishing the testing tooling itself.
