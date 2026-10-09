import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

// proxy.ts imports ACCESS_COOKIE from lib/auth/cookies.ts, which is `import "server-only"`-guarded
// (correctly — it's never meant to run in the browser); that guard throws outside Next.js's own
// react-server build condition, which plain vitest doesn't set. Stub it for this module-level test.
vi.mock("server-only", () => ({}));

const { ACCESS_COOKIE } = await import("@/lib/auth/cookies");
const { proxy } = await import("./proxy");

function requestFor(pathname: string, { loggedIn = false }: { loggedIn?: boolean } = {}): NextRequest {
  return new NextRequest(`https://app.example.test${pathname}`, {
    headers: loggedIn ? { cookie: `${ACCESS_COOKIE}=token` } : undefined,
  });
}

describe("proxy", () => {
  it("lets an anonymous request through to widget.js, the embeddable widget's public script", () => {
    // widget.js (public/widget.js) is loaded by anonymous visitors on third-party sites that
    // embedded it — they never hold this app's session cookie. Redirecting them to this app's own
    // login page instead of the script silently breaks the widget everywhere it's embedded.
    const res = proxy(requestFor("/widget.js"));
    expect(res.status).toBe(200);
  });

  it("still redirects an anonymous request away from a real protected page", () => {
    const res = proxy(requestFor("/admin/dashboard"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("https://app.example.test/");
  });

  it("lets a logged-in request through to a protected page", () => {
    const res = proxy(requestFor("/admin/dashboard", { loggedIn: true }));
    expect(res.status).toBe(200);
  });
});
