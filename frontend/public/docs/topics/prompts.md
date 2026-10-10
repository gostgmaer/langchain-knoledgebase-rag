Prompts are versioned templates for an agent's system prompt. Every edit creates a **new version**
instead of overwriting the last one, so nothing is ever silently lost — rolling back to an earlier
wording is just publishing that older version again.

**Prompts → New prompt** asks for a name, description, and category, then creates the prompt with
no text yet — open its **Versions** panel to actually write one:

1. Type the template text into **New draft version**, optionally with a short changelog note on
   what changed — it shows up in the version history later, when "why did this change" is exactly
   what you'll want to know.
2. **Save as new draft** — it's stored, but not live yet.
3. **Publish** — makes that version the one agents referencing this prompt actually use. The
   previously-live version stays in the history, badged by its status (draft, or a past published
   version), not deleted.

The prompt list itself shows each one's category, a preview of its currently live version, and
whether it's active.

![Prompt version history](/docs/images/prompts-versions.png)
