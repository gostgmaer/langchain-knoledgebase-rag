The directory of every organization (tenant) on the platform, and which one you're currently
browsing as. The table shows each tenant's name (flagged if it's the platform's **default**
tenant), active/inactive status, and when it was created.

**Browse as** switches your session into that tenant's workspace — handy for support and setup
without needing a separate account in every tenant. Recently-viewed tenants are listed as
quick-access shortcuts above the full table, remembered locally in your browser.

Loading this directory itself needs the real IAM permission `tenant:read_all`, which today only
the `super_admin` role actually has — if the directory fails to load, that permission is the first
thing to check, not a bug in this page.

![Tenant directory with browse-as shortcuts](/docs/images/tenants-directory.png)
