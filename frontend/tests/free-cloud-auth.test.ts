import { expect, it, vi } from "vitest";

vi.hoisted(() => {
  process.env.NEXT_PUBLIC_AUTH_MODE = "cloudflare";
});

import { getIdToken, handleSignInCallback, isFreeCloud } from "@/lib/auth";

it("uses the same-origin session without Cognito or exposing a cookie token", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({ owner: "owner" }),
  } as Response);
  expect(isFreeCloud).toBe(true);
  expect(await getIdToken()).toBe("cookie-session");
  expect((await handleSignInCallback())?.idToken).toBe("cookie-session");
  expect(await getIdToken()).toBe("cookie-session");
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledWith("/api/me", { cache: "no-store" });
});
