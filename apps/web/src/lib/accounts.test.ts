/* eslint-disable @typescript-eslint/no-unused-vars -- typed fake deps keep the real signatures */
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Role } from "@hrm/shared";
import type { Session } from "./access";
import {
  assignManagerWith,
  changeRoleWith,
  createAccountWith,
  linkGuardianWith,
  mergeAccounts,
  resetPasswordWith,
  setAccountDisabledWith,
  unlinkGuardianWith,
  type AccountInfo,
  type AccountsDeps,
} from "./accounts";

const admin: Session = { uid: "admin1", role: "admin" };
const staffCaller: Session = { uid: "s", role: "staff" };
const PW = "correct-horse-battery";

type Acc = { role?: Role; disabled?: boolean };

function makeDeps(opts: { accounts?: Record<string, Acc>; people?: string[]; enabledAdmins?: number } = {}) {
  const accounts = opts.accounts ?? {};
  const people = new Set(opts.people ?? ["P1"]);
  const calls: string[] = [];
  const track = <A extends unknown[], R>(name: string, fn: (...a: A) => Promise<R>) =>
    vi.fn(async (...a: A) => {
      calls.push(name);
      return fn(...a);
    });
  const deps = {
    createUser: track("createUser", async (_a: { email: string; password: string; displayName?: string }) => ({
      uid: "new1",
    })),
    deleteUser: track("deleteUser", async (_uid: string) => {}),
    updateUser: track("updateUser", async (_uid: string, _p: { disabled?: boolean; password?: string }) => {}),
    setClaims: track("setClaims", async (_uid: string, _c: { role: Role; personId?: string }) => {}),
    revokeSessions: track("revokeSessions", async (_uid: string) => {}),
    writeUser: track("writeUser", async (_uid: string, _d: Record<string, unknown>) => {}),
    deleteMarker: Symbol("delete"),
    personExists: track("personExists", async (id: string) => people.has(id)),
    getAccount: track("getAccount", async (uid: string): Promise<AccountInfo | null> => {
      const a = accounts[uid];
      return a ? { uid, role: a.role, disabled: a.disabled === true } : null;
    }),
    countEnabledAdmins: track("countEnabledAdmins", async () => opts.enabledAdmins ?? 2),
    linkGuardian: track("linkGuardian", async (_p: string, _u: string) => {}),
    unlinkGuardian: track("unlinkGuardian", async (_p: string, _u: string) => {}),
    setManager: track("setManager", async (_p: string, _u: string | null) => {}),
  };
  return { deps: deps as unknown as AccountsDeps & typeof deps, calls };
}

afterEach(() => vi.restoreAllMocks());

describe("non-admin callers are rejected with zero dep calls", () => {
  const cases: [string, (d: AccountsDeps, c: Session | null) => Promise<unknown>][] = [
    ["createAccount", (d, c) => createAccountWith(d, c, { email: "a@b.co", password: PW, role: "admin" })],
    ["changeRole", (d, c) => changeRoleWith(d, c, "u1", "manager")],
    ["setAccountDisabled", (d, c) => setAccountDisabledWith(d, c, "u1", true)],
    ["resetPassword", (d, c) => resetPasswordWith(d, c, "u1", PW)],
    ["linkGuardian", (d, c) => linkGuardianWith(d, c, "P1", "g1")],
    ["unlinkGuardian", (d, c) => unlinkGuardianWith(d, c, "P1", "g1")],
    ["assignManager", (d, c) => assignManagerWith(d, c, "P1", "m1")],
  ];
  for (const [name, run] of cases) {
    for (const caller of [staffCaller, null]) {
      it(`${name} (${caller ? caller.role : "no session"})`, async () => {
        const { deps, calls } = makeDeps();
        await expect(run(deps, caller)).rejects.toThrow("Forbidden: admin only");
        expect(calls).toEqual([]);
      });
    }
  }
});

describe("createAccount", () => {
  const base = { email: "a@b.co", password: PW };

  it("rejects staff without personId", async () => {
    const { deps, calls } = makeDeps();
    const r = await createAccountWith(deps, admin, { ...base, role: "staff" });
    expect(r.ok).toBe(false);
    expect(calls).toEqual([]);
  });
  it("rejects staff with unknown person", async () => {
    const { deps } = makeDeps();
    const r = await createAccountWith(deps, admin, { ...base, role: "staff", personId: "NOPE" });
    expect(r).toEqual({ ok: false, error: expect.stringContaining("not found") });
    expect(deps.createUser).not.toHaveBeenCalled();
  });
  it("rejects guardian with personId", async () => {
    const { deps } = makeDeps();
    const r = await createAccountWith(deps, admin, { ...base, role: "guardian", personId: "P1" });
    expect(r.ok).toBe(false);
    expect(deps.createUser).not.toHaveBeenCalled();
  });
  it("rejects short password and bad email and bad role", async () => {
    const { deps } = makeDeps();
    expect((await createAccountWith(deps, admin, { ...base, password: "short", role: "admin" })).ok).toBe(false);
    expect((await createAccountWith(deps, admin, { ...base, email: "nope", role: "admin" })).ok).toBe(false);
    expect((await createAccountWith(deps, admin, { ...base, role: "root" as Role })).ok).toBe(false);
    expect(deps.createUser).not.toHaveBeenCalled();
  });
  it("writes claims with exactly {role}", async () => {
    const { deps } = makeDeps();
    const r = await createAccountWith(deps, admin, { ...base, role: "guardian" });
    expect(r).toEqual({ ok: true, uid: "new1" });
    const claims = deps.setClaims.mock.calls[0]![1];
    expect(Object.keys(claims)).toEqual(["role"]);
    expect(deps.createUser).toHaveBeenCalledWith({ email: "a@b.co", password: PW, displayName: undefined });
  });
  it("writes claims with exactly {role, personId} and mirrors the users doc", async () => {
    const { deps } = makeDeps();
    const r = await createAccountWith(deps, admin, { ...base, displayName: "Sam", role: "staff", personId: "P1" });
    expect(r.ok).toBe(true);
    const claims = deps.setClaims.mock.calls[0]![1];
    expect(Object.keys(claims).sort()).toEqual(["personId", "role"]);
    const [uid, doc] = deps.writeUser.mock.calls[0]!;
    expect(uid).toBe("new1");
    expect(doc).toEqual({ role: "staff", personId: "P1", displayName: "Sam", email: "a@b.co" });
  });
  it("optional personId for manager must exist", async () => {
    const { deps } = makeDeps();
    expect((await createAccountWith(deps, admin, { ...base, role: "manager", personId: "NOPE" })).ok).toBe(false);
    expect((await createAccountWith(deps, admin, { ...base, role: "manager" })).ok).toBe(true);
  });
  it("rolls back the created user when the claims write fails", async () => {
    const { deps } = makeDeps();
    deps.setClaims.mockRejectedValueOnce(new Error("boom"));
    const r = await createAccountWith(deps, admin, { ...base, role: "admin" });
    expect(r.ok).toBe(false);
    expect(deps.deleteUser).toHaveBeenCalledWith("new1");
    expect(deps.writeUser).not.toHaveBeenCalled();
  });
  it("rolls back when the users doc write fails", async () => {
    const { deps } = makeDeps();
    deps.writeUser.mockRejectedValueOnce(new Error("boom"));
    const r = await createAccountWith(deps, admin, { ...base, role: "admin" });
    expect(r.ok).toBe(false);
    expect(deps.deleteUser).toHaveBeenCalledWith("new1");
  });
  it("maps email-already-exists", async () => {
    const { deps } = makeDeps();
    deps.createUser.mockRejectedValueOnce(Object.assign(new Error("x"), { code: "auth/email-already-exists" }));
    const r = await createAccountWith(deps, admin, { ...base, role: "admin" });
    expect(r).toEqual({ ok: false, error: expect.stringContaining("already") });
    expect(deps.deleteUser).not.toHaveBeenCalled();
  });
  it("never echoes or logs the password", async () => {
    const spies = (["log", "error", "warn", "info"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
    const { deps } = makeDeps();
    deps.setClaims.mockRejectedValueOnce(new Error(`bad ${PW}`));
    const bad = await createAccountWith(deps, admin, { ...base, role: "admin" });
    const ok = await createAccountWith(deps, admin, { ...base, role: "admin" });
    const short = await createAccountWith(deps, admin, { ...base, password: "short", role: "admin" });
    for (const r of [bad, ok, short]) expect(JSON.stringify(r)).not.toContain(PW);
    for (const s of spies) expect(JSON.stringify(s.mock.calls)).not.toContain(PW);
  });
});

describe("changeRole", () => {
  it("goes through applyUserRole (claims, then revoke, then doc)", async () => {
    const { deps, calls } = makeDeps({ accounts: { u1: { role: "guardian" } } });
    const r = await changeRoleWith(deps, admin, "u1", "staff", "P1");
    expect(r).toEqual({ ok: true });
    expect(calls.indexOf("setClaims")).toBeGreaterThan(-1);
    expect(calls.indexOf("revokeSessions")).toBeGreaterThan(calls.indexOf("setClaims"));
    expect(deps.setClaims).toHaveBeenCalledWith("u1", { role: "staff", personId: "P1" });
  });
  it("applies personId rules", async () => {
    const { deps } = makeDeps({ accounts: { u1: { role: "guardian" } } });
    expect((await changeRoleWith(deps, admin, "u1", "staff")).ok).toBe(false);
    expect((await changeRoleWith(deps, admin, "u1", "staff", "NOPE")).ok).toBe(false);
    expect((await changeRoleWith(deps, admin, "u1", "guardian", "P1")).ok).toBe(false);
    expect(deps.setClaims).not.toHaveBeenCalled();
  });
  it("rejects unknown account", async () => {
    const { deps } = makeDeps();
    expect((await changeRoleWith(deps, admin, "ghost", "manager")).ok).toBe(false);
  });
  it("blocks self-demotion", async () => {
    const { deps } = makeDeps({ accounts: { admin1: { role: "admin" } } });
    const r = await changeRoleWith(deps, admin, "admin1", "manager");
    expect(r).toEqual({ ok: false, error: expect.stringContaining("yourself") });
    expect(deps.setClaims).not.toHaveBeenCalled();
  });
  it("blocks demoting the last enabled admin", async () => {
    const { deps } = makeDeps({ accounts: { other: { role: "admin" } }, enabledAdmins: 1 });
    const r = await changeRoleWith(deps, admin, "other", "manager");
    expect(r).toEqual({ ok: false, error: expect.stringContaining("last") });
    expect(deps.setClaims).not.toHaveBeenCalled();
  });
  it("allows demoting an admin when others remain", async () => {
    const { deps } = makeDeps({ accounts: { other: { role: "admin" } }, enabledAdmins: 2 });
    expect((await changeRoleWith(deps, admin, "other", "manager")).ok).toBe(true);
  });
  it("allows demoting a disabled admin even if only one enabled admin", async () => {
    const { deps } = makeDeps({ accounts: { other: { role: "admin", disabled: true } }, enabledAdmins: 1 });
    expect((await changeRoleWith(deps, admin, "other", "manager")).ok).toBe(true);
  });
});

describe("setAccountDisabled", () => {
  it("blocks disabling yourself", async () => {
    const { deps } = makeDeps({ accounts: { admin1: { role: "admin" } } });
    const r = await setAccountDisabledWith(deps, admin, "admin1", true);
    expect(r.ok).toBe(false);
    expect(deps.updateUser).not.toHaveBeenCalled();
  });
  it("blocks disabling the last enabled admin", async () => {
    const { deps } = makeDeps({ accounts: { other: { role: "admin" } }, enabledAdmins: 1 });
    const r = await setAccountDisabledWith(deps, admin, "other", true);
    expect(r).toEqual({ ok: false, error: expect.stringContaining("last") });
    expect(deps.updateUser).not.toHaveBeenCalled();
  });
  it("disables and revokes", async () => {
    const { deps, calls } = makeDeps({ accounts: { u1: { role: "staff" } } });
    expect(await setAccountDisabledWith(deps, admin, "u1", true)).toEqual({ ok: true });
    expect(deps.updateUser).toHaveBeenCalledWith("u1", { disabled: true });
    expect(calls.indexOf("revokeSessions")).toBeGreaterThan(calls.indexOf("updateUser"));
  });
  it("enables without revoking or guard checks", async () => {
    const { deps } = makeDeps({ accounts: { admin1: { role: "admin", disabled: true } }, enabledAdmins: 0 });
    expect(await setAccountDisabledWith(deps, admin, "admin1", false)).toEqual({ ok: true });
    expect(deps.updateUser).toHaveBeenCalledWith("admin1", { disabled: false });
    expect(deps.revokeSessions).not.toHaveBeenCalled();
  });
  it("rejects unknown account", async () => {
    const { deps } = makeDeps();
    expect((await setAccountDisabledWith(deps, admin, "ghost", true)).ok).toBe(false);
  });
});

describe("resetPassword", () => {
  it("rejects short password", async () => {
    const { deps } = makeDeps();
    expect((await resetPasswordWith(deps, admin, "u1", "short")).ok).toBe(false);
    expect(deps.updateUser).not.toHaveBeenCalled();
  });
  it("updates then revokes sessions and never leaks the password", async () => {
    const spies = (["log", "error", "warn", "info"] as const).map((m) =>
      vi.spyOn(console, m).mockImplementation(() => {}),
    );
    const { deps, calls } = makeDeps();
    const r = await resetPasswordWith(deps, admin, "u1", PW);
    expect(r).toEqual({ ok: true });
    expect(deps.updateUser).toHaveBeenCalledWith("u1", { password: PW });
    expect(calls.indexOf("revokeSessions")).toBeGreaterThan(calls.indexOf("updateUser"));
    deps.updateUser.mockRejectedValueOnce(new Error(`failed with ${PW}`));
    const bad = await resetPasswordWith(deps, admin, "u1", PW);
    expect(bad.ok).toBe(false);
    expect(JSON.stringify(bad)).not.toContain(PW);
    for (const s of spies) expect(JSON.stringify(s.mock.calls)).not.toContain(PW);
  });
});

describe("linkGuardian / unlinkGuardian", () => {
  it("links a guardian account, idempotently", async () => {
    const { deps } = makeDeps({ accounts: { g1: { role: "guardian" } } });
    expect(await linkGuardianWith(deps, admin, "P1", "g1")).toEqual({ ok: true });
    expect(await linkGuardianWith(deps, admin, "P1", "g1")).toEqual({ ok: true });
    expect(deps.linkGuardian).toHaveBeenCalledWith("P1", "g1");
  });
  it("rejects non-guardian account, unknown account, unknown person", async () => {
    const { deps } = makeDeps({ accounts: { m1: { role: "manager" }, g1: { role: "guardian" } } });
    expect((await linkGuardianWith(deps, admin, "P1", "m1")).ok).toBe(false);
    expect((await linkGuardianWith(deps, admin, "P1", "ghost")).ok).toBe(false);
    expect((await linkGuardianWith(deps, admin, "NOPE", "g1")).ok).toBe(false);
    expect(deps.linkGuardian).not.toHaveBeenCalled();
  });
  it("unlink is ok for a non-linked uid and requires the person", async () => {
    const { deps } = makeDeps();
    expect(await unlinkGuardianWith(deps, admin, "P1", "whoever")).toEqual({ ok: true });
    expect(deps.unlinkGuardian).toHaveBeenCalledWith("P1", "whoever");
    expect((await unlinkGuardianWith(deps, admin, "NOPE", "g1")).ok).toBe(false);
  });
});

describe("assignManager", () => {
  it("assigns a manager or admin account", async () => {
    const { deps } = makeDeps({ accounts: { m1: { role: "manager" }, a2: { role: "admin" } } });
    expect(await assignManagerWith(deps, admin, "P1", "m1")).toEqual({ ok: true });
    expect(await assignManagerWith(deps, admin, "P1", "a2")).toEqual({ ok: true });
    expect(deps.setManager).toHaveBeenCalledWith("P1", "m1");
  });
  it("rejects staff/guardian/unknown accounts and unknown person", async () => {
    const { deps } = makeDeps({ accounts: { s1: { role: "staff" }, g1: { role: "guardian" }, m1: { role: "manager" } } });
    expect((await assignManagerWith(deps, admin, "P1", "s1")).ok).toBe(false);
    expect((await assignManagerWith(deps, admin, "P1", "g1")).ok).toBe(false);
    expect((await assignManagerWith(deps, admin, "P1", "ghost")).ok).toBe(false);
    expect((await assignManagerWith(deps, admin, "NOPE", "m1")).ok).toBe(false);
    expect(deps.setManager).not.toHaveBeenCalled();
  });
  it("clears with null", async () => {
    const { deps } = makeDeps();
    expect(await assignManagerWith(deps, admin, "P1", null)).toEqual({ ok: true });
    expect(deps.setManager).toHaveBeenCalledWith("P1", null);
    expect(deps.getAccount).not.toHaveBeenCalled();
  });
});

describe("mergeAccounts", () => {
  const users = [
    {
      uid: "u1",
      email: "a@x.co",
      displayName: "Ann",
      disabled: false,
      customClaims: { role: "staff", personId: "P1" },
      metadata: { lastSignInTime: "Thu, 01 Jan 2026 00:00:00 GMT" },
    },
    { uid: "u2", email: "b@x.co", disabled: true, customClaims: {}, metadata: {} },
    { uid: "u3", email: "c@x.co", disabled: false, customClaims: { role: "bogus" }, metadata: {} },
    { uid: "u4", disabled: false, customClaims: { role: "manager", personId: "GONE" }, metadata: {} },
  ];
  const rows = mergeAccounts(users, new Map([["P1", { name: "Pat" }]]));
  it("labels role and linked person", () => {
    expect(rows[0]).toMatchObject({
      uid: "u1",
      role: "staff",
      roleLabel: "staff",
      personId: "P1",
      personName: "Pat",
      disabled: false,
    });
    expect(rows[0]!.lastSignIn).toBe("2026-01-01T00:00:00.000Z");
  });
  it("flags accounts with no valid role", () => {
    expect(rows[1]).toMatchObject({ role: null, roleLabel: "no role (cannot sign in)", disabled: true, lastSignIn: null });
    expect(rows[2]!.role).toBeNull();
  });
  it("handles missing person doc and missing email", () => {
    expect(rows[3]).toMatchObject({ personId: "GONE", personName: null, email: "" });
  });
});
