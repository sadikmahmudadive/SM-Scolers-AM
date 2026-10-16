import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("./firebase-admin", () => ({ getAdminDb: vi.fn() }));

import type { PersonWithId } from "./attendance-loader";
import { loadChildren, loadPersonDays, loadSelectedDays, loadSelf, loadTeam, type ScopedDeps } from "./scoped-loaders";
import type { ScopedSpec } from "./scoped-queries";

const person = (id: string): PersonWithId => ({
  id,
  name: id,
  kind: "student",
  guardianUids: [],
  deviceEnrolled: false,
  active: true,
  createdAt: new Date(0),
});

function deps(over: Partial<ScopedDeps> = {}): ScopedDeps {
  return {
    queryPeople: vi.fn(async () => [] as PersonWithId[]),
    getPerson: vi.fn(async (id: string) => person(id)),
    queryPunches: vi.fn(async () => []),
    ...over,
  } as ScopedDeps;
}

describe("loadTeam", () => {
  it("queries ONLY with the session uid", async () => {
    const d = deps({ queryPeople: vi.fn(async () => [person("a"), person("b")]) });
    const r = await loadTeam({ uid: "m1", role: "manager" }, d);
    expect(d.queryPeople).toHaveBeenCalledTimes(1);
    expect(d.queryPeople).toHaveBeenCalledWith({
      collection: "people",
      where: [["managerId", "==", "m1"]],
      limit: 60,
    });
    expect(r.reports.map((p) => p.id)).toEqual(["a", "b"]);
    expect(r.truncated).toBe(false);
  });
  it("empty list is not an error", async () => {
    expect(await loadTeam({ uid: "m1", role: "manager" }, deps())).toEqual({ reports: [], truncated: false });
  });
  it("flags truncation at the limit", async () => {
    const many = Array.from({ length: 60 }, (_, i) => person(`p${i}`));
    const r = await loadTeam({ uid: "m1", role: "manager" }, deps({ queryPeople: vi.fn(async () => many) }));
    expect(r.truncated).toBe(true);
  });
  it("admin gets no special broadening", async () => {
    const d = deps();
    await loadTeam({ uid: "adm", role: "admin" }, d);
    expect(d.queryPeople).toHaveBeenCalledWith({
      collection: "people",
      where: [["managerId", "==", "adm"]],
      limit: 60,
    });
  });
});

describe("loadChildren", () => {
  it("queries ONLY guardianUids array-contains uid", async () => {
    const d = deps({ queryPeople: vi.fn(async () => [person("c1")]) });
    const r = await loadChildren({ uid: "g1", role: "guardian" }, d);
    expect(d.queryPeople).toHaveBeenCalledWith({
      collection: "people",
      where: [["guardianUids", "array-contains", "g1"]],
      limit: 20,
    });
    expect(r.children).toHaveLength(1);
  });
  it("empty is fine", async () => {
    expect((await loadChildren({ uid: "g1", role: "guardian" }, deps())).children).toEqual([]);
  });
});

describe("loadSelf", () => {
  it("no personId -> linked false and no deps call", async () => {
    const d = deps();
    expect(await loadSelf({ uid: "s", role: "staff" }, d)).toEqual({ linked: false });
    expect(d.getPerson).not.toHaveBeenCalled();
    expect(d.queryPeople).not.toHaveBeenCalled();
    expect(d.queryPunches).not.toHaveBeenCalled();
  });
  it("loads only session.personId", async () => {
    const d = deps();
    const r = await loadSelf({ uid: "s", role: "staff", personId: "p9" }, d);
    expect(d.getPerson).toHaveBeenCalledWith("p9");
    expect(r).toMatchObject({ linked: true, person: { id: "p9" } });
  });
  it("linked to a missing person is not linked", async () => {
    const d = deps({ getPerson: vi.fn(async () => null) });
    expect(await loadSelf({ uid: "s", role: "staff", personId: "gone" }, d)).toEqual({ linked: false });
  });
});

describe("loadPersonDays / IDOR", () => {
  const range = { from: "2026-03-01", to: "2026-03-02" };
  it("queries punches for the personId with the attendance spec", async () => {
    const d = deps();
    await loadPersonDays("p1", range, d);
    expect(d.queryPunches).toHaveBeenCalledWith({
      collection: "attendance",
      where: [
        ["personId", "==", "p1"],
        ["date", ">=", "2026-03-01"],
        ["date", "<=", "2026-03-02"],
      ],
      orderBy: ["date", "desc"],
      limit: 500,
    });
  });
  it("loadSelectedDays loads attendance only for ids in the scoped set", async () => {
    const d = deps();
    const r = await loadSelectedDays("foreign", ["a", "b"], range, d);
    expect(r?.personId).toBe("a");
    const calls = (d.queryPunches as ReturnType<typeof vi.fn>).mock.calls as Array<[ScopedSpec]>;
    expect(calls).toHaveLength(1);
    expect(calls[0][0].where[0][2]).toBe("a");
  });
  it("loadSelectedDays keeps an allowed id", async () => {
    const d = deps();
    const r = await loadSelectedDays("b", ["a", "b"], range, d);
    expect(r?.personId).toBe("b");
  });
  it("loadSelectedDays with empty set loads nothing", async () => {
    const d = deps();
    expect(await loadSelectedDays("x", [], range, d)).toBeNull();
    expect(d.queryPunches).not.toHaveBeenCalled();
  });
});
