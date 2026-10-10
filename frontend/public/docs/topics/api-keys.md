For calling this platform's API from your own code — a script, a CI pipeline, a Zapier integration
— independent of a browser session. Create one under **API Keys → New API key**, name it something
that says what it's for ("CI pipeline", "Zapier integration"), and send it as
`Authorization: Bearer <key>` on requests. Every key acts with full admin access to this tenant, so
treat it like a password, not a scoped token.

The key is shown once, at creation — copy it immediately, it can't be retrieved again afterward.
The list after that shows only its name, a short prefix (enough to recognize which key is which,
not the key itself), who created it, when it was last used ("never" until it is), and its status.
**Revoke** disables a key immediately and can't be undone — create a new one in its place.

![API key created, shown once](/docs/images/api-key-created.png)
