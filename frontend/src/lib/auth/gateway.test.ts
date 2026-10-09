import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// gateway.ts is `import "server-only"`-guarded (correctly — it's never meant to run in the
// browser); that guard throws outside Next.js's own react-server build condition, which plain
// vitest doesn't set. Stub it for this module-level unit test only.
vi.mock("server-only", () => ({}));

const { gatewayRefresh } = await import("./gateway");

const tokenResponse = (accessToken: string) => ({
  ok: true,
  json: async () => ({ success: true, data: { accessToken, refreshToken: "new-refresh" } }),
});

describe("gatewayRefresh", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("coalesces concurrent calls for the same refresh token into one gateway request", async () => {
    // A page load's GET /api/auth/session racing several GET /api/rag/* calls can all decide the
    // access token is expired at once and all read the same (still valid) refresh-token cookie
    // before any of them has written a new one back.
    let resolveFetch: (value: unknown) => void = () => {};
    fetchMock.mockImplementation(
      () => new Promise((resolve) => { resolveFetch = resolve; }),
    );

    const first = gatewayRefresh("same-refresh-token", "https://app.example.test");
    const second = gatewayRefresh("same-refresh-token", "https://app.example.test");

    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveFetch(tokenResponse("access-1"));
    const [a, b] = await Promise.all([first, second]);

    expect(a.accessToken).toBe("access-1");
    expect(b.accessToken).toBe("access-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not coalesce calls for different refresh tokens", async () => {
    fetchMock
      .mockResolvedValueOnce(tokenResponse("access-a"))
      .mockResolvedValueOnce(tokenResponse("access-b"));

    const [a, b] = await Promise.all([
      gatewayRefresh("token-a", "https://app.example.test"),
      gatewayRefresh("token-b", "https://app.example.test"),
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(a.accessToken).toBe("access-a");
    expect(b.accessToken).toBe("access-b");
  });

  it("issues a fresh gateway call once a prior refresh for the same token has settled", async () => {
    fetchMock
      .mockResolvedValueOnce(tokenResponse("access-1"))
      .mockResolvedValueOnce(tokenResponse("access-2"));

    const first = await gatewayRefresh("same-refresh-token", "https://app.example.test");
    const second = await gatewayRefresh("same-refresh-token", "https://app.example.test");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(first.accessToken).toBe("access-1");
    expect(second.accessToken).toBe("access-2");
  });
});
