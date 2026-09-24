// Tab-scoped hand-off between "opened an invite link while signed out" and
// "now signed in" (password login or social redirect — both end on the login
// page, which reads this and forwards to /accept-invite). sessionStorage, not
// localStorage: an abandoned invite shouldn't hijack a login days later.
export const PENDING_INVITE_KEY = "rag-console-pending-invite";
