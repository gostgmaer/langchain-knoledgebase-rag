For calling this platform's API from your own code — a script, a CI pipeline, a Zapier integration
— independent of a browser session. Create one under **API Keys → New API key**, name it something
that says what it's for ("CI pipeline", "Zapier integration"), and send it as
`Authorization: Bearer <key>` on requests. The key is shown once, at creation — copy it immediately,
it can't be retrieved again afterward (only revoked and replaced with a new one).

![API key created, shown once](/docs/images/api-key-created.png)
