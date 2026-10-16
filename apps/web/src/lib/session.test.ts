import { describe, expect, it, vi } from "vitest";
import { claimsToSession, decideAccess, homeFor } from "./access";
import { applyUserRole } from "./user-role";

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
  const mk = () => ({ setClaims: vi.fn(async () => {}), writeUser: vi.fn(async () => {}) });

  it("rejects a non-admin caller without side effects", async () => {
    const deps = mk();
    await expect(applyUserRole(deps, { uid: "c", role: "staff" }, "u1", "admin")).rejects.toThrow();
    await expect(applyUserRole(deps, null, "u1", "admin")).rejects.toThrow();
    expect(deps.setClaims).not.toHaveBeenCalled();
    expect(deps.writeUser).not.toHaveBeenCalled();
  });

  it("rejects an invalid role", async () => {
    const deps = mk();
    await expect(
      applyUserRole(deps, { uid: "c", role: "admin" }, "u1", "root" as never),
    ).rejects.toThrow();
    expect(deps.setClaims).not.toHaveBeenCalled();
  });

  it("sets claims and writes the user doc for an admin", async () => {
    const deps = mk();
    await applyUserRole(deps, { uid: "c", role: "admin" }, "u1", "guardian", "p1");
    expect(deps.setClaims).toHaveBeenCalledWith("u1", { role: "guardian", personId: "p1" });
    expect(deps.writeUser).toHaveBeenCalledWith("u1", { role: "guardian", personId: "p1" });
  });
});
