import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { applyScopedSpec, childrenSpec, personAttendanceSpec, resolveSelection, teamPeopleSpec } from "./scoped-queries";

describe("specs", () => {
  it("teamPeopleSpec scopes by managerId", () => {
    expect(teamPeopleSpec("u1")).toEqual({
      collection: "people",
      where: [["managerId", "==", "u1"]],
      limit: 60,
    });
  });
  it("childrenSpec scopes by guardianUids", () => {
    expect(childrenSpec("g1")).toEqual({
      collection: "people",
      where: [["guardianUids", "array-contains", "g1"]],
      limit: 20,
    });
  });
  it("personAttendanceSpec", () => {
    expect(personAttendanceSpec("p1", { from: "2026-01-01", to: "2026-01-31" })).toEqual({
      collection: "attendance",
      where: [
        ["personId", "==", "p1"],
        ["date", ">=", "2026-01-01"],
        ["date", "<=", "2026-01-31"],
      ],
      orderBy: ["date", "desc"],
      limit: 500,
    });
  });
  it("personAttendanceSpec matches the (personId asc, date desc) composite index", () => {
    const path = fileURLToPath(new URL("../../../../firebase/firestore.indexes.json", import.meta.url));
    const json = JSON.parse(readFileSync(path, "utf8")) as {
      indexes: Array<{ collectionGroup: string; fields: Array<{ fieldPath: string; order: string }> }>;
    };
    const spec = personAttendanceSpec("p", { from: "a", to: "b" });
    expect(spec.where[0][0]).toBe("personId");
    expect(spec.orderBy).toEqual(["date", "desc"]);
    const found = json.indexes.some(
      (i) =>
        i.collectionGroup === "attendance" &&
        i.fields.length === 2 &&
        i.fields[0].fieldPath === "personId" &&
        i.fields[0].order === "ASCENDING" &&
        i.fields[1].fieldPath === "date" &&
        i.fields[1].order === "DESCENDING",
    );
    expect(found).toBe(true);
  });
});

describe("applyScopedSpec", () => {
  it("chains where, orderBy and limit", () => {
    const calls: unknown[][] = [];
    const q: Record<string, (...a: unknown[]) => unknown> = {
      where: (...a) => (calls.push(["where", ...a]), q),
      orderBy: (...a) => (calls.push(["orderBy", ...a]), q),
      limit: (...a) => (calls.push(["limit", ...a]), q),
    };
    const db = { collection: (n: string) => (calls.push(["collection", n]), q) };
    applyScopedSpec(db as never, personAttendanceSpec("p1", { from: "a", to: "b" }));
    expect(calls).toEqual([
      ["collection", "attendance"],
      ["where", "personId", "==", "p1"],
      ["where", "date", ">=", "a"],
      ["where", "date", "<=", "b"],
      ["orderBy", "date", "desc"],
      ["limit", 500],
    ]);
  });
  it("skips orderBy when absent", () => {
    const calls: string[] = [];
    const q: Record<string, (...a: unknown[]) => unknown> = {
      where: () => (calls.push("where"), q),
      orderBy: () => (calls.push("orderBy"), q),
      limit: () => (calls.push("limit"), q),
    };
    applyScopedSpec({ collection: () => q } as never, teamPeopleSpec("u"));
    expect(calls).toEqual(["where", "limit"]);
  });
});

describe("resolveSelection", () => {
  it("keeps an allowed id", () => expect(resolveSelection("b", ["a", "b"])).toBe("b"));
  it("replaces a foreign id with the first allowed", () => expect(resolveSelection("x", ["a", "b"])).toBe("a"));
  it("returns null for an empty set", () => expect(resolveSelection("a", [])).toBeNull());
  it("handles undefined input", () => expect(resolveSelection(undefined, ["a"])).toBe("a"));
  it("undefined input with empty set", () => expect(resolveSelection(undefined, [])).toBeNull());
});
