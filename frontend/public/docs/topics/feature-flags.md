Dynamic toggles for app behavior that take effect without a redeploy.

**New flag** asks for a **Key** (the code-level identifier, e.g. `enable_rbac`), a **Scope**, and
an optional description. Scope is either **Global default** — applies to everyone — or one
specific tenant picked from the directory, which overrides the global value for that tenant only.
A flag is created disabled by default; flip it with the switch in the list once you're ready.

The list shows each flag's key, scope (a tenant's name, or a **global** badge), description, and
an on/off switch you can toggle directly — no separate save step. **Delete** removes the flag
entirely; its effective value then falls back to whatever the default would otherwise be, so
deleting an override is a safe way to revert a tenant back to the global behavior.

![Feature flags list](/docs/images/feature-flags-list.png)
