Some connectors (Confluence, SharePoint/OneDrive, Teams, private Slack channels) carry their own
access rules — who could see a page or file in the *original* system. Meridian can mirror those
rules so the same people (and only those people) can retrieve that content in chat here too.

On a source's detail page, the **Permissions** tab shows:

- **Default visibility** — who can see content from this source when it carries no specific
  access rule of its own: everyone in the tenant, or just administrators plus selected roles.
- **Identity mappings** — the link between an *external* identity (a Confluence/SharePoint user or
  group id, a Slack or Teams user id) and an *internal* one (a Meridian user, or a role). Add a
  mapping by entering the external id, choosing whether it's a **user** or a **group**, and
  choosing what it maps to internally. Getting the user/group choice right matters: a mapping
  saved as the wrong type silently never matches anything, so access never actually applies even
  though the mapping itself saved successfully.

![Permissions tab with identity mappings](/docs/images/permissions-tab.png)

If a source can't enumerate page-level permissions at all (some Confluence setups, for instance),
its content falls back to the source's own default visibility setting above.
