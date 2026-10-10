A Model Profile is a configured LLM (and/or embedding model) connection — provider, model name, and
context window — that agents and retrieval run on. Model Profiles are shared platform-wide, not
scoped to one workspace.

**New model profile** asks for a **Name**, **Provider**, **Model**, and **Context window** (in
tokens). The list then shows each profile's provider/model, context window, which capabilities it
reports (streaming, tools, embeddings — informational, not something this form sets directly), and
its status. **Disable** takes a profile out of use without deleting its configuration; **Enable**
brings it back.

Exactly one profile can be the platform's **default** at a time, shown as a badge next to its name
— that's the one used anywhere a profile isn't explicitly chosen, including when
[creating an agent](/docs/agents).

![Model Profiles list](/docs/images/model-profiles-list.png)
