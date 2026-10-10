Who's actually in this workspace, and anyone invited but not yet joined.

- **Members** lists real accounts in this workspace, with name, email, and whether the account is
  active. It does not show which specific role each member holds — only that they're a member;
  manage per-member roles through IAM directly if you need to check or change one.
- **Invite a teammate** sends an email with a join link. New recipients create an account (or sign
  in with Google, Microsoft or Facebook using the same address); existing account holders just
  accept. Pick a role from the dropdown — it defaults to the ordinary "member" role when one
  exists; platform-level roles (super admin, service accounts) are deliberately left out of this
  list, since they're not something you hand out from an invite form.
- Invitations expire after **7 days** — resend by inviting again if one lapses. **Invitations**
  below the invite form lists every pending or past invite with its role and expiry date; a
  pending one can be **Revoked** before it's accepted.

![Team members and pending invitations](/docs/images/team-members.png)
