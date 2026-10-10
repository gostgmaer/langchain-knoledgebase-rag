Operational knobs that apply platform-wide, not per workspace — rate limits, CORS origins,
retention windows, and similar. Secrets and anything that controls who can do what (API keys,
whether auth is required, which roles count as admin) are deliberately never exposed here; those
stay environment-variable-only, outside the reach of this page.

Each field shows its current value, or its built-in default as a placeholder when it hasn't been
overridden — an **overridden** badge appears next to any field you've changed, with a button to
reset it back to that default. Fields render according to their type: a number input (with
min/max where they apply), a dropdown when only specific choices are valid, a plain text field, a
toggle switch for on/off settings, or a list of entries (like allowed origins) you add to and
remove from individually. Changes apply within about 30 seconds — no restart needed.

![Platform settings form](/docs/images/platform-settings.png)
