An Agent is a reusable assistant configuration: which system prompt it uses, which
[Model Profile](/docs/model-profiles) it runs on, and its sampling parameters (temperature, and
similar). Rather than re-entering these every time, define an agent once — **Agents → New agent**
— and chat (or the [embeddable widget](/docs/embeddable-widget)) uses it directly.

**Creating or editing one** asks for:

- **Name** and **Description** — how you'll recognize it in the list.
- **System prompt** — the instructions it always starts a conversation with.
- **LLM provider** and **LLM model** — which backend actually generates its answers.
- **Model profile** — picked from the platform's configured [Model Profiles](/docs/model-profiles);
  required before the agent can be created.

The list shows each agent's provider/model, temperature, and status — **Deactivate** turns one off
without deleting it (chat can no longer select it; **Activate** brings it back). Editing an
existing agent also exposes its [embeddable chat widget](/docs/embeddable-widget) settings.

![Agents list](/docs/images/agents-list.png)
