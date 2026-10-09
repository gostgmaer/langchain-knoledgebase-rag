Any agent can be exposed as a small chat widget you embed on an external website — your marketing
site, a support portal, anywhere outside Meridian itself.

1. Open the agent, turn on **Embeddable chat widget**.
2. Add the exact origins (scheme + host + port, no path) allowed to use it — leaving this empty
   means no origin is allowed, so set it before you need the widget live.
3. Save. An **embed snippet** appears: a single `<script>` tag referencing this agent. Paste it
   into the target site's HTML.

If the widget is ever compromised or you just want a clean break, **Rotate widget id** invalidates
the current snippet immediately — update it wherever it's embedded afterward, or the old snippet
stops working.

![Agent widget settings with embed snippet](/docs/images/widget-embed.png)
