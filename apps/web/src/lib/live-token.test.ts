import { describe, expect, it } from "vitest";
import { decideLiveTokenRequest, REFRESH_AFTER_MS, shouldRefreshToken, shouldScheduleRefresh } from "./live-token";

describe("decideLiveTokenRequest", () => {
  const base = { origin: null, requestOrigin: "http://x", session: { uid: "u", role: "admin" as const } };
  it("401 without session", () => {
    expect(decideLiveTokenRequest({ ...base, session: null })).toMatchObject({ kind: "reject", status: 401 });
  });
  it("403 cross-origin", () => {
    expect(decideLiveTokenRequest({ ...base, origin: "http://evil" })).toMatchObject({ kind: "reject", status: 403 });
  });
  it("ok for same-origin or no origin header, with claims", () => {
    expect(decideLiveTokenRequest(base)).toEqual({ kind: "ok", uid: "u", claims: { role: "admin" } });
    expect(
      decideLiveTokenRequest({ ...base, origin: "http://x", session: { uid: "u", role: "staff", personId: "7" } }),
    ).toEqual({ kind: "ok", uid: "u", claims: { role: "staff", personId: "7" } });
  });
});

describe("shouldRefreshToken", () => {
  it("refreshes only once past the refresh point", () => {
    expect(shouldRefreshToken(0, REFRESH_AFTER_MS)).toBe(false);
    expect(shouldRefreshToken(0, REFRESH_AFTER_MS + 1)).toBe(true);
  });
  it("refreshes when never fetched", () => {
    expect(shouldRefreshToken(null, 1)).toBe(true);
  });
});

describe("shouldScheduleRefresh", () => {
  it("only while listeners are active", () => {
    expect(shouldScheduleRefresh(0)).toBe(false);
    expect(shouldScheduleRefresh(2)).toBe(true);
  });
});
