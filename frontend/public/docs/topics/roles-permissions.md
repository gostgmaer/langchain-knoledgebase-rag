Every account is exactly one of three roles, and the role decides which pages even show up in the
sidebar — not just which buttons are disabled on a shared page.

| Role | Sees | Scope |
| --- | --- | --- |
| **Customer** | Chat, Documentation, Settings. Nothing else — that's the whole menu for this role, not a trimmed-down view of something bigger. | One tenant (workspace). |
| **Tenant Admin** | Everything a Customer sees, plus Dashboard, Knowledge Bases, Knowledge Sources, Documents, Search, Agents, Model Profiles, Prompts, Tools, Analytics, Retrieval Log, Retrieval Settings, Observability, Usage, Feedback, Upload Jobs, Team, and API Keys. | One tenant. |
| **Admin** | Everything a Tenant Admin sees, plus Tenants, Feature Flags, and Platform Settings. | The whole platform, across every tenant. |

A page missing from your sidebar isn't a bug to report — it means your role genuinely doesn't have
it. Hiding the link is also not the only thing stopping you: typing a hidden page's URL directly
doesn't get you in either, it redirects you back to your own home page.

**Admin browsing a tenant.** [Tenants](/docs/tenants)' **Browse as** lets an Admin view one
tenant's data (Documents, Agents, Analytics, and so on) without creating a separate account in it.
This only changes *which tenant's data loads* — it doesn't narrow an Admin down to a Tenant Admin's
menu. An Admin browsing a tenant still sees every Admin-only page too; they're just now looking at
that tenant's Dashboard, documents, and so on instead of their own.

Model Profiles are the one exception to "scoped to one tenant" above: they're shared
platform-wide, visible and editable by both Tenant Admins and Admins, not owned by any single
tenant.

![Role comparison](/docs/images/roles-permissions.png)
