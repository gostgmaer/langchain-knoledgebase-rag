**Chat didn't cite the document I expected.**
Confirm the knowledge source containing it has finished syncing (check its status on
[Knowledge Sources](/docs/knowledge-sources) — "connected" with a recent "Last sync" time, not
"error" or "disconnected"), and that your account has access to it (see
[Permissions and identity mappings](/docs/permissions)). Also check
[Retrieval Settings](/docs/retrieval) — a relevance threshold set too high can exclude a
genuinely relevant but lower-scoring passage.

**A knowledge source shows "error" or "disconnected."**
Open its detail page — the most recent sync run usually explains why (expired credentials, a
revoked permission, a source temporarily unreachable). Reconnecting usually means re-entering
credentials and letting the next sync run.

**I added an identity mapping but access still isn't working.**
Double-check the mapping's principal type — "user" vs. "group" — matches what you actually meant
to map. A mapping saved as the wrong type looks successful but silently never matches anything.

**The embeddable widget isn't loading on my site.**
Confirm the site's exact origin (scheme + host + port) is in the agent's allowed-origins list, and
that the widget is still enabled — rotating the widget id invalidates every snippet issued before
the rotation.

**My invitation link expired.**
Invitations expire 7 days after they're sent. Ask whoever invited you to send a new one from
[Team](/docs/team).

**I can't see a page mentioned in this guide.**
Some pages are role-specific — see [Getting started](/docs/getting-started) for what each role's
menu actually includes. If you believe you should have access to something you don't see, ask your
workspace administrator.
