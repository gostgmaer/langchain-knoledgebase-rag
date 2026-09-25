# QA report - RAG platform (UI, API, IAM integration)

Test date: 2026-09-25. Stack: local Docker (IAM, gateway, notification, file-upload, Mailpit, RAG API/worker) + Next.js dev server.
Every finding below was reproduced against the running stack unless marked **(code review)**.

## 1. Summary

| # | Severity | Finding | Status |
|---|---|---|---|
| B1 | **High** | Any signed-in **member** can create and toggle **global feature flags** (including the master `enable_rbac` switch) | Open |
| B2 | **High** | **Open self-registration** puts anyone in the admin's workspace as `member`, with read access to its data | Open (product decision) |
| B3 | **Medium** | A member can read admin-only data and open admin-only pages by URL (analytics, usage, feedback, model profiles, prompts, tools, agents, feature flags) and can create knowledge bases | Open |
| B4 | **Medium** | The super-admin **"browse as tenant"** feature no longer works: the API now ignores the tenant header (regression from my IAM-enforcement change) | Open (mine) |
| B5 | **Medium** | New **social-login users have no workspace** and cannot get one without an admin invite | Partly fixed (clear screen); no way forward |
| B6 | **Medium** | **Invite into a second workspace does nothing** for a user who already has the default one (member cannot switch) | Open (IAM role design) |
| B7 | Low | Provider outage (Gemini 503) surfaces as **HTTP 500** "unexpected internal server error" | Open |
| B8 | Low | Six views have **no error state**: analytics, usage, search, document detail, dashboard, feedback | Open (code review) |
| B9 | Low | **No DELETE** for knowledge bases or feature flags (405); test/mistaken rows cannot be removed from the UI or API | Open |
| B10 | Low | Email verification is not required: unverified accounts can sign in and use the API | Open |
| B11 | Low | Frontend lint: 3 errors (`react-hooks/set-state-in-effect`) in files unrelated to recent work | Open |
| B12 | Info | IAM login rate limit is easy to hit (429) during repeated logins; how the UI words a 429 was not verified | Note |
| Fixed | - | Crash (HTTP 500) for accounts without a workspace -> now 403 + "You are not in a workspace yet" screen (commit `9f601d9`) | Done |
| Fixed | - | Microsoft sign-in failed with `AADSTS9002325` -> Entra redirect URI must be type **Web**, not SPA; now reaches Microsoft's sign-in page | Done |
| Fixed | - | Microsoft ignored the tenant in env (IAM database setting overrode it) -> setting updated | Done |

## 2. What was tested

**Automated (all passing):** RAG Python suite **125 passed**; IAM `tsc` clean + **42/42** tests; frontend `tsc` clean; env preflight **0 FAIL**; end-to-end API script `scripts/e2e_local.sh` **24/24** (login, IAM enforcement, spoof protection, invite email + register, upload -> ingestion, chat with citations, social redirects); 17 containers healthy.

**Browser (logged out):** login page, register page (with and without invite banner), `/accept-invite`, `/auth/callback?error=`, protected-route redirect, Google account chooser (client + redirect URI accepted), Microsoft sign-in page reached. Console: no errors or warnings. Accessibility tree: inputs and buttons have accessible names.

**Signed-in screens, replayed through the same `/api/rag` proxy the UI uses**, as **super admin** and as **member**: all 16 pages render (HTTP 200) for both roles; all data endpoints return 200 for both roles (see B3).

## 3. Not tested (and why)

- **Signed-in screens clicked in a browser.** The browser session was signed out and I do not enter passwords. Team invite form, upload dialog, chat streaming, settings buttons, and every CRUD dialog are verified by API and code review only.
- **A complete Google/Microsoft login** (needs your account at the provider). Facebook is not configured.
- **Whether both OAuth redirect URIs are registered in each provider console** beyond what the providers accept on the first hop.
- **Mobile/responsive layout** and the **frontend production build** (would corrupt the running dev server's cache).
- How the UI words an IAM **429** (rate limit) response.

## 4. Findings in detail

### B1 - Members can create and toggle feature flags (High)
- **Repro:** signed in as a `member`: `POST /api/rag/feature-flags {"key":"x","enabled":false}` -> **201** with `tenant_id: null` (a global flag). `PATCH /feature-flags/{id}/toggle {"enabled":true}` -> **200**.
- **Cause:** the router's admin check (`require_role("admin")`) only enforces when the `enable_rbac` flag is on; it is off, so the check does nothing. Feature flags control retrieval, tools, reranking, streaming and `enable_rbac` itself.
- **Suggestion:** attach the existing `require_admin()` (active with `AUTH_REQUIRED=true`) to the feature-flag router's write routes now, independent of `enable_rbac`; also protect who may create **global** (`tenant_id null`) flags (super admin only). Add a test that a member gets 403.

### B2 - Open self-registration joins the admin workspace (High)
- **Repro:** `POST /api/auth/register` with no invite -> 201; login works; `/me` shows the **same tenant as the admin**, role `member`, `isEmailVerified: false`; `GET /api/rag/knowledge-bases` -> **200**. Setting `auth.registration.enabled = true`.
- **Impact:** in a private deployment a stranger can register and ask chat about the workspace's documents.
- **Suggestion (pick per deployment):** turn registration off (`auth.registration.enabled=false`) and use invites only; or require email verification before access; or create a new workspace per sign-up instead of using the default; and restrict which knowledge bases a `member` can query.

### B3 - Members see admin-only data and pages (Medium)
- **Repro:** member session: `/api/rag/{feature-flags, analytics/summary, usage, feedback, model-profiles, prompts, tool-definitions, agents}` all **200**; pages `/customer/analytics`, `/customer/usage`, `/customer/feature-flags`, `/customer/tenants`, `/customer/team`... render. Creating prompts, tools and agents is correctly **403**, but `POST /knowledge-bases` -> **201**. The sidebar hides these pages for customers, but nothing stops opening the URL.
- **Suggestion:** decide which reads are admin-only and guard them server-side (`require_admin`), then add a per-page role check in the UI (redirect or "not allowed" screen). Decide whether members may create knowledge bases.

### B4 - "Browse as tenant" broken for super admin (Medium, regression)
- **Cause:** `require_uuid_header` now returns the verified token's tenant and ignores `X-Tenant-ID` (to stop spoofing). The frontend still sends the header when a super admin picks another tenant on the Tenants page, so the admin keeps seeing their own tenant's data.
- **Suggestion:** allow the header override only when the verified user has the `super_admin` role (ideally also audit-log it); keep ignoring it for everyone else.

### B5 - Social sign-up users have no workspace (Medium)
- **Repro:** `kishor81160@gmail.com` (created by Google sign-in) has no `tenantId` in IAM. Before: every request 500. Now: 403 with a clear message and the "You are not in a workspace yet" screen.
- **Still missing:** nothing lets that user get a workspace except an admin invite.
- **Suggestion:** add a "Create my workspace" step, or auto-add social sign-ups to the default workspace **only if** B2 is resolved, or show the invite request flow ("ask your admin").

### B6 - Invites into another workspace have no effect for existing members (Medium)
- **Repro:** created a second tenant, invited a new email; the invitee registered, but `/me` still returns the **default** tenant and `POST /api/tenants/switch` -> **403 "Insufficient permissions"** for `member`.
- **Cause:** registration always adds a default-tenant membership, and `member` lacks the switch permission. Invites only work for users with no other workspace (like the Google case).
- **Suggestion:** grant switch permission to members (for tenants they belong to), or stop auto-adding the default tenant when an invite token is used.

### B7 - Provider outage returned as HTTP 500 (Low)
- Gemini `503 UNAVAILABLE ... high demand` (after client retries) becomes **500 "An unexpected internal server error"** with no hint. **Suggestion:** map provider errors to 503/502 with a retry message; show it in the chat UI.

### B8 - Views without an error state (Low, code review)
- `analytics-view`, `usage-view`, `search-view`, `document-detail-view`, `dashboard-view`, `feedback-view` handle loading but not failure: a 403/500 leaves an empty or stuck screen. **Suggestion:** one shared `QueryError` component (message + retry) used by every view.

### B9 - No DELETE for knowledge bases / feature flags (Low)
- `DELETE` returns **405**. Probe rows had to be removed with SQL. **Suggestion:** add admin-only delete (soft delete for knowledge bases, with confirmation in the UI).

### B10 - Email verification not enforced (Low)
- Unverified accounts sign in and use the API. **Suggestion:** require verification (IAM `AUTH_REGISTRATION_REQUIRE_EMAIL_VERIFY`) and show a "verify your email" screen.

### B11 - Lint errors (Low)
- 3 `react-hooks/set-state-in-effect` errors in `[role]/chat/page.tsx`, `[role]/tenants/page.tsx`, `hooks/use-conversation-history.ts`. **Suggestion:** derive state during render or use `useSyncExternalStore` for the `localStorage` history; escape the apostrophe in the tenants page.

### B12 - Login rate limiting (Info)
- Repeated logins returned **429** quickly during testing. Confirm the UI shows "too many attempts, wait a minute" instead of a generic failure.

## 5. Suggested order of work

1. **B1** feature-flag write protection (small, high impact).
2. **B2** decide registration policy (config change) and **B10** email verification.
3. **B3** server-side guards for admin-only reads + UI page guards.
4. **B4** super-admin tenant override (restores a lost feature).
5. **B5 / B6** workspace onboarding: self-service workspace or auto-membership, and member switch permission.
6. **B7 / B8** error handling (provider outages, shared error component).
7. **B9 / B11 / B12** housekeeping.

## 6. Pending (not bugs)

**Needs you**
- Sign in as super admin in the browser so the signed-in screens can be clicked through (Team invite, upload, chat, settings).
- Complete a real **Google** and **Microsoft** login; confirm both redirect URIs (`http://localhost:3301/api/auth/social/<provider>/callback`) in each console; Microsoft app must be type **Web**.
- **Facebook**: create the app and add `FACEBOOK_APP_ID` / `FACEBOOK_APP_SECRET`, or leave it off.
- Confirm the file-upload service's MongoDB (Atlas) accepts this machine.
- Decide B2 (registration policy) and B5 (how a new user gets a workspace).

**Engineering**
- Production: add GitHub secret `BACKUP_CODE_ENCRYPTION_KEY`, provider secrets, generate production secrets and change the dev bootstrap password, then run the manual `deploy-infra` workflow. The RAG API and frontend are not part of the infra env generator yet.
- Nothing has been **pushed**. Local branches: RAG `feat/iam-enforcement-and-cleanup`; IAM `fix/social-login-verified-email-linking`; easydev-infra `feat/iam-social-login-env`. New per-repo `docs/DEPENDENCIES.md` files in the other service repos are **uncommitted**.
- IAM `.env`/infra env files were edited locally (gitignored); backups are in the assistant scratchpad.
- Placeholders that are intentional: RAG `IAM_CLIENT_ID/SECRET`, dev bootstrap passwords.

**Test leftovers in the local database** (safe to delete): throwaway users `e2e.invitee.*`, `e2e2.invitee.*`, `inviteA.*`, `intruderB.*`, `noinvite.*`, `reuse.*`, `rbac.probe.*`; workspace "E2E Co"; test documents `smoke.txt`, `e2e_doc*.txt`, `test document` files in the admin workspace; test conversations.
