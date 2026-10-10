Two kinds of tools an agent can call during a conversation:

- **Built-in** — always available, not editable here: `calculator`, `get_weather`, `get_news`,
  `get_google_search`, `search_knowledge_base`, `search_document`, `lookup_iam_user`, and
  `lookup_iam_tenant`.
- **Definitions you create** under **Tools → New tool definition** — a **Name**, a **Description**
  (this is what the LLM itself reads to decide when to call it, so be specific), and a **Category**.
  Only the **CUSTOM** category with a **Webhook URL** filled in becomes a real, callable tool:
  pick **POST** (the tool's input arrives as a JSON body, `{ input }`) or **GET** (as a query
  parameter, `?input=...`). Every other category is saved as metadata only, for now — useful for
  documenting a capability before it's wired up, but an agent can't actually invoke it.

A custom tool missing its URL shows a warning in the list instead of silently doing nothing.

![Tools list, built-in and custom](/docs/images/tools-list.png)
