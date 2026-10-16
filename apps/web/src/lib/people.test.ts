import { describe, expect, it, vi } from "vitest";
import {
  createPersonWith,
  deletePersonWith,
  importPeopleCsvWith,
  updatePersonWith,
  type PeopleDeps,
} from "./people";

const admin = { uid: "a", role: "admin" as const };
const staff = { uid: "s", role: "staff" as const };
const NOW = new Date("2026-02-02T00:00:00Z");

function makeDeps(existing: string[] = [], batchSize?: number) {
  const store = new Set(existing);
  const deps = {
    now: () => NOW,
    deleteMarker: "DEL",
    batchSize,
    create: vi.fn(async (id: string, ...rest: [Record<string, unknown>]) => {
      void rest;
      if (store.has(id)) throw Object.assign(new Error("exists"), { code: 6 });
      store.add(id);
    }),
    update: vi.fn(async (...args: [string, Record<string, unknown>]) => void args),
    remove: vi.fn(async (...args: [string]) => void args),
    existingIds: vi.fn(async (ids: string[]) => new Set(ids.filter((i) => store.has(i)))),
    createMany: vi.fn(async (items: { id: string; data: Record<string, unknown> }[]) => {
      for (const i of items) store.add(i.id);
    }),
  } satisfies PeopleDeps;
  return deps;
}

describe("non-admin callers", () => {
  it("are rejected with no writes", async () => {
    const d = makeDeps();
    await expect(createPersonWith(d, staff, { id: "1", name: "A", kind: "student" })).rejects.toThrow(/admin/);
    await expect(updatePersonWith(d, staff, "1", { name: "B" })).rejects.toThrow(/admin/);
    await expect(deletePersonWith(d, null, "1")).rejects.toThrow(/admin/);
    await expect(importPeopleCsvWith(d, staff, "id,name\n1,A\n")).rejects.toThrow(/admin/);
    expect(d.create).not.toHaveBeenCalled();
    expect(d.update).not.toHaveBeenCalled();
    expect(d.remove).not.toHaveBeenCalled();
    expect(d.createMany).not.toHaveBeenCalled();
  });
});

describe("createPersonWith", () => {
  it("creates with defaults", async () => {
    const d = makeDeps();
    const r = await createPersonWith(d, admin, { id: "42", name: "Ann", kind: "teacher", phone: "" });
    expect(r).toEqual({ ok: true });
    expect(d.create).toHaveBeenCalledWith("42", {
      name: "Ann",
      kind: "teacher",
      guardianUids: [],
      deviceEnrolled: false,
      active: true,
      createdAt: NOW,
    });
  });
  it("rejects an invalid kind", async () => {
    const d = makeDeps();
    const r = await createPersonWith(d, admin, { id: "1", name: "A", kind: "alien" as never });
    expect(r.ok).toBe(false);
    expect(d.create).not.toHaveBeenCalled();
  });
  it("rejects a bad id", async () => {
    const d = makeDeps();
    for (const id of ["", "a/b", "x y"]) {
      expect((await createPersonWith(d, admin, { id, name: "A", kind: "staff" })).ok).toBe(false);
    }
    expect(d.create).not.toHaveBeenCalled();
  });
  it("rejects an existing id", async () => {
    const d = makeDeps(["1"]);
    const r = await createPersonWith(d, admin, { id: "1", name: "A", kind: "staff" });
    expect(r).toEqual({ ok: false, error: expect.stringContaining("already exists") });
  });
});

describe("updatePersonWith", () => {
  it("cannot change id or createdAt, clears blank optionals", async () => {
    const d = makeDeps();
    const r = await updatePersonWith(d, admin, "1", {
      name: "New",
      phone: "",
      id: "999",
      createdAt: new Date(0),
    } as never);
    expect(r).toEqual({ ok: true });
    expect(d.update).toHaveBeenCalledWith("1", { name: "New", phone: "DEL" });
  });
  it("rejects an invalid kind", async () => {
    const d = makeDeps();
    expect((await updatePersonWith(d, admin, "1", { kind: "x" as never })).ok).toBe(false);
    expect(d.update).not.toHaveBeenCalled();
  });
  it("maps not-found", async () => {
    const d = makeDeps();
    d.update.mockRejectedValueOnce(Object.assign(new Error("nf"), { code: 5 }));
    expect(await updatePersonWith(d, admin, "1", { name: "x" })).toEqual({ ok: false, error: "Person not found" });
  });
});

describe("deletePersonWith", () => {
  it("only removes the people doc", async () => {
    const d = makeDeps();
    expect(await deletePersonWith(d, admin, "5")).toEqual({ ok: true });
    expect(d.remove).toHaveBeenCalledTimes(1);
    expect(d.remove).toHaveBeenCalledWith("5");
    // PeopleDeps exposes no attendance-deleting capability at all.
    expect(Object.keys(d).filter((k) => /attend/i.test(k))).toEqual([]);
  });
});

describe("importPeopleCsvWith", () => {
  it("skips existing ids and writes only new ones in batches", async () => {
    const d = makeDeps(["2"], 2);
    const csv = "id,name\n1,A\n2,B\n3,C\n4,D\n5,\n";
    const r = await importPeopleCsvWith(d, admin, csv);
    expect(r.imported).toBe(3);
    expect(r.errors).toEqual(
      expect.arrayContaining([
        { row: 3, message: expect.stringContaining("already exists") },
        { row: 6, message: expect.stringContaining("name") },
      ]),
    );
    expect(d.createMany).toHaveBeenCalledTimes(2);
    const written = d.createMany.mock.calls.flatMap((c) => c[0].map((i) => i.id));
    expect(written).toEqual(["1", "3", "4"]);
    expect(d.createMany.mock.calls[0]?.[0][0]?.data).toMatchObject({
      guardianUids: [],
      deviceEnrolled: false,
      active: true,
      createdAt: NOW,
    });
  });
  it("rejects files over 1 MB", async () => {
    const d = makeDeps();
    const r = await importPeopleCsvWith(d, admin, "x".repeat(1024 * 1024 + 1));
    expect(r.imported).toBe(0);
    expect(r.errors[0]?.message).toMatch(/large/i);
    expect(d.createMany).not.toHaveBeenCalled();
  });
  it("reports a failed batch as row errors", async () => {
    const d = makeDeps();
    d.createMany.mockRejectedValueOnce(new Error("boom"));
    const r = await importPeopleCsvWith(d, admin, "id,name\n1,A\n");
    expect(r.imported).toBe(0);
    expect(r.errors).toEqual([{ row: 2, message: expect.stringContaining("boom") }]);
  });
});
