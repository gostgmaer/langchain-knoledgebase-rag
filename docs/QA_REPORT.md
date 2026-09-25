# QA report - RAG platform (UI, API, IAM integration)

Test date: 2026-09-25. Stack: local Docker (IAM, gateway, notification, file-upload, Mailpit, RAG API/worker) + Next.js dev server.
Every finding below was reproduced against the running stack unless marked **(code review)**.

## 1. Summary (updated after the fixes)

| # | Severity | Finding | Status |
|---|---|---|---|
| B1 | **High** | Members could create/toggle **global feature flags** (incl. `enable_rbac`) | **Fixed** - admin-only always; global flags need a platform admin; tenant admins limited to their own tenant's flags |
| B2 | **High** | **Open self-registration** put anyone in the admin workspace, and IAM's `auth.registration.enabled` setting was **not enforced at all** | **Fixed** in IAM (invite-only enforced for password and social sign-up). Local instance is now **invite-only** |
| B3 | **Medium** | Members could read admin-only data and open admin pages by URL; could create knowledge bases | **Fixed** - server: every non-chat route is admin-only; UI: per-page role guard |
| B4 | **Medium** | Super-admin "browse as tenant" broken by my earlier change | **Fixed** - `X-Tenant-ID` honoured for `TENANT_OVERRIDE_ROLES` (default `super_admin`) only |
| B5 | **Medium** | New social users had no workspace | **Resolved by B2**: unknown emails can no longer create stranded accounts in invite-only mode. Existing stranded accounts still need an invite |
| B6 | **Medium** | Invite into a second workspace had no effect | **Fixed for sign-up** (an invitee registers into *only* the invited workspace). **Not changed:** an existing user accepting an invite still cannot switch workspace (member lacks the switch permission) |
| B7 | Low | Provider outage returned HTTP 500 | **Fixed** - mapped to 503 + `Retry-After` with a clear message (unit-tested; not reproduced live) |
| B8 | Low | Six views had no error state | **Fixed** - shared `QueryError` component with retry |
| B9 | Low | No DELETE for knowledge bases / feature flags | **Fixed** - API + UI buttons (KB only when empty) |
| B10 | Low | Email verification not enforced | **Option added** - `REQUIRE_VERIFIED_EMAIL` (off by default; unit-tested). Turn on with IAM verification for public deployments |
| B11 | Low | 3 lint errors | **Fixed** - frontend `tsc` and `eslint` now report **0 problems** |
| B12 | Info | Raw 429 text on rate-limited login | **Fixed** - friendly message (code only; not triggered in a browser) |
| Earlier | - | No-workspace crash (500), Microsoft `AADSTS9002325`, Microsoft tenant setting | Fixed before this round |

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

## 4. Findings in detail (original write-up; see the table above for current status)

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

## 7. Fix log and verification

**What changed**
- **RAG API:** `require_admin()` on every admin-only router (knowledge bases, documents, agents, prompts, tools, model profiles, usage, analytics, upload jobs, feedback list, feature flags); feature-flag rules (`_may_manage`: global flags = platform admin only, tenant admin = own tenant only) plus `DELETE /feature-flags/{id}`; `DELETE /knowledge-bases/{id}` (empty only, else 409); `TENANT_OVERRIDE_ROLES`; `REQUIRE_VERIFIED_EMAIL`; provider outages -> 503 + `Retry-After`.
- **IAM:** `assertRegistrationAllowed` / `findUsableInvitation` enforced in `register()` and in the first social sign-up; invitee into a non-default workspace as plain member no longer also joins the default workspace.
- **Frontend:** per-page role guard (`isAllowedPath`), shared `QueryError` + error states in six views, delete buttons (knowledge bases, feature flags), invite-only login/register pages, friendly 429 message, 0 lint problems.
- **Config/docs:** `.env.example`, `ENVIRONMENT.md`, IAM `INTEGRATION.md`.

**Verification (live, rebuilt stack)**
- Live script: **48/48** (invite-only refusal and acceptance, member 403 on all 14 checked routes, admin CRUD incl. flag and KB delete, KB-with-documents 409, super-admin override honoured and member override ignored, tenant-2 invitee lands only in tenant 2).
- `scripts/e2e_local.sh`: **37/37**. IAM: **52/52** tests (10 new), `tsc` clean. Frontend: `tsc` and `eslint` **0 problems**. RAG unit tests for every new rule (`test_authorization_fixes.py`, `test_auth_no_tenant.py`).
- Browser (logged out): login shows "Sign-up is by invitation only"; `/register` shows the invitation-only page, and with `?inviteToken=` shows the form.

**Behaviour changes to be aware of**
- The local IAM is now **invite-only**. To reopen sign-up: `PUT /api/iam/settings/auth.registration.enabled {"value":false}` -> `true`. The setting is stored in IAM's database, not in an env file.
- Plain members now see **only Chat and Settings**; direct URLs to other pages show "You don't have access to this page" and their APIs return 403.
- `X-Tenant-ID` is ignored for everyone except `TENANT_OVERRIDE_ROLES`.

**Still open / not verified**
- Signed-in screens in a browser (the session was signed out; I do not enter passwords): the new role-guard page, `QueryError` states, delete buttons and the 429 message are verified by type-check, lint and API only.
- Existing users accepting an invite into a second workspace still cannot switch (member lacks the permission) - needs an IAM permission/UX decision.
- The stranded account `kishor81160@gmail.com` still needs an admin invite.
- Provider-outage 503 was unit-tested but not reproduced against a real Gemini outage.
- A real Google/Microsoft login end to end, and Facebook.
