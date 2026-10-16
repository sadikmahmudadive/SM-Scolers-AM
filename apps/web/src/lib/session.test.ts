import { describe, expect, it, vi } from "vitest";
import { claimsToSession, decideAccess, homeFor } from "./access";
import { applyUserRole } from "./user-role";
import { assertNoEmulatorInProduction } from "./emulator-guard";
import { evaluateSessionRequest } from "./session-request";

describe("homeFor", () => {
  it("maps each role to its home", () => {
    expect(homeFor("admin")).toBe("/dashboard");
    expect(homeFor("manager")).toBe("/team");
    expect(homeFor("staff")).toBe("/me");
    expect(homeFor("guardian")).toBe("/children");
  });
});

describe("decideAccess", () => {
  it("redirects to /login without a session", () => {
    expect(decideAccess(null, ["admin"])).toEqual({ kind: "redirect", to: "/login" });
  });
  it("redirects a disallowed role to its home", () => {
    expect(decideAccess({ uid: "u", role: "staff" }, ["admin"])).toEqual({ kind: "redirect", to: "/me" });
  });
  it("allows an allowed role", () => {
    expect(decideAccess({ uid: "u", role: "admin" }, ["admin"])).toEqual({ kind: "ok" });
  });
});

describe("claimsToSession", () => {
  it("rejects a token without a valid role", () => {
    expect(claimsToSession({ uid: "u" })).toBeNull();
    expect(claimsToSession({ uid: "u", role: "root" })).toBeNull();
  });
  it("maps role and personId", () => {
    expect(claimsToSession({ uid: "u", role: "guardian", personId: "p1" })).toEqual({
      uid: "u",
      role: "guardian",
      personId: "p1",
    });
    expect(claimsToSession({ uid: "u", role: "staff" })).toEqual({ uid: "u", role: "staff" });
  });
});

describe("applyUserRole", () => {
  const DEL = Symbol("delete");
  const mk = () => {
    const order: string[] = [];
    return {
      order,
      setClaims: vi.fn(async () => { order.push("setClaims"); }),
      revokeSessions: vi.fn(async () => { order.push("revoke"); }),
      writeUser: vi.fn(async () => { order.push("write"); }),
      deleteMarker: DEL as unknown,
    };
  };
  const admin = { uid: "c", role: "admin" as const };

  it("rejects a non-admin caller without side effects", async () => {
    const deps = mk();
    await expect(applyUserRole(deps, { uid: "c", role: "staff" }, "u1", "admin")).rejects.toThrow();
    await expect(applyUserRole(deps, null, "u1", "admin")).rejects.toThrow();
    expect(deps.setClaims).not.toHaveBeenCalled();
    expect(deps.revokeSessions).not.toHaveBeenCalled();
    expect(deps.writeUser).not.toHaveBeenCalled();
  });

  it("rejects an invalid role without side effects", async () => {
    const deps = mk();
    await expect(applyUserRole(deps, admin, "u1", "root" as never)).rejects.toThrow();
    expect(deps.setClaims).not.toHaveBeenCalled();
    expect(deps.revokeSessions).not.toHaveBeenCalled();
  });

  it("sets claims, revokes sessions after, and writes the user doc", async () => {
    const deps = mk();
    await applyUserRole(deps, admin, "u1", "guardian", "p1");
    expect(deps.setClaims).toHaveBeenCalledWith("u1", { role: "guardian", personId: "p1" });
    expect(deps.revokeSessions).toHaveBeenCalledWith("u1");
    expect(deps.order.indexOf("revoke")).toBeGreaterThan(deps.order.indexOf("setClaims"));
    expect(deps.writeUser).toHaveBeenCalledWith("u1", { role: "guardian", personId: "p1" });
  });

  it("omits personId from claims and deletes it from the doc when absent", async () => {
    const deps = mk();
    await applyUserRole(deps, admin, "u1", "staff");
    const claims = (deps.setClaims.mock.calls[0] as unknown as [string, object])[1];
    expect(Object.keys(claims)).toEqual(["role"]);
    expect(deps.writeUser).toHaveBeenCalledWith("u1", { role: "staff", personId: DEL });
  });
});

describe("assertNoEmulatorInProduction", () => {
  const names = ["FIREBASE_AUTH_EMULATOR_HOST"];
  it("throws in production with an emulator var", () => {
    expect(() => assertNoEmulatorInProduction({ NODE_ENV: "production", FIREBASE_AUTH_EMULATOR_HOST: "x:1" }, names)).toThrow();
  });
  it("is fine in development", () => {
    expect(() => assertNoEmulatorInProduction({ NODE_ENV: "development", FIREBASE_AUTH_EMULATOR_HOST: "x:1" }, names)).not.toThrow();
  });
  it("is fine in production without the var", () => {
    expect(() => assertNoEmulatorInProduction({ NODE_ENV: "production" }, names)).not.toThrow();
  });
});

describe("evaluateSessionRequest", () => {
  const now = 1_000_000;
  const base = {
    contentType: "application/json",
    origin: "http://a.test",
    requestOrigin: "http://a.test",
    decoded: { uid: "u", role: "staff", auth_time: now - 10 },
    nowSec: now,
  };
  it("accepts a valid request", () => {
    expect(evaluateSessionRequest(base)).toEqual({ kind: "ok", session: { uid: "u", role: "staff" } });
    expect(evaluateSessionRequest({ ...base, origin: null }).kind).toBe("ok");
  });
  it("rejects bad content type", () => {
    expect(evaluateSessionRequest({ ...base, contentType: "text/plain" })).toMatchObject({ kind: "reject", status: 415 });
  });
  it("rejects cross-origin", () => {
    expect(evaluateSessionRequest({ ...base, origin: "http://evil.test" })).toMatchObject({ kind: "reject", status: 403 });
  });
  it("rejects a missing role with 403", () => {
    expect(evaluateSessionRequest({ ...base, decoded: { uid: "u", auth_time: now - 10 } })).toMatchObject({ kind: "reject", status: 403 });
  });
  it("rejects a stale sign-in with 401", () => {
    expect(evaluateSessionRequest({ ...base, decoded: { uid: "u", role: "staff", auth_time: now - 301 } })).toMatchObject({ kind: "reject", status: 401 });
  });
});
