import { describe, expect, it } from "vitest";
import type { Attendance, Person } from "@hrm/shared";
import { filterAndPage, logsQuerySpec, summarizeToday } from "./attendance-queries";

const person = (over: Partial<Person> = {}): Person => ({
  name: "P",
  kind: "student",
  guardianUids: [],
  deviceEnrolled: true,
  active: true,
  createdAt: new Date(0),
  ...over,
});

const punch = (personId: string, iso: string, over: Partial<Attendance> = {}): Attendance => ({
  personId,
  ts: new Date(iso),
  date: iso.slice(0, 10),
  status: "present",
  direction: "in",
  deviceId: "d1",
  late: false,
  earlyLeave: false,
  ...over,
});

describe("logsQuerySpec", () => {
  it("builds inclusive date range ordered by date asc with limit 5000", () => {
    const s = logsQuerySpec({ from: "2026-01-01", to: "2026-01-31" });
    expect(s.where).toEqual([
      ["date", ">=", "2026-01-01"],
      ["date", "<=", "2026-01-31"],
    ]);
    expect(s.orderBy).toEqual(["date", "asc"]);
    expect(s.limit).toBe(5000);
  });
  it("adds personId equality", () => {
    const s = logsQuerySpec({ from: "2026-01-01", to: "2026-01-01", personId: "42" });
    expect(s.where).toContainEqual(["personId", "==", "42"]);
  });
  it("throws when from > to or dates malformed", () => {
    expect(() => logsQuerySpec({ from: "2026-02-01", to: "2026-01-01" })).toThrow();
    expect(() => logsQuerySpec({ from: "bad", to: "2026-01-01" })).toThrow();
  });
});

describe("filterAndPage", () => {
  const people = new Map<string, Person>([
    ["1", person({ kind: "student", className: "A" })],
    ["2", person({ kind: "teacher" })],
    ["3", person({ kind: "student", className: "B" })],
  ]);
  const punches = [
    punch("1", "2026-01-01T01:00:00Z"),
    punch("2", "2026-01-01T03:00:00Z"),
    punch("3", "2026-01-01T02:00:00Z"),
    punch("9", "2026-01-01T04:00:00Z"),
  ];
  const f = { from: "2026-01-01", to: "2026-01-01" };

  it("sorts newest first and keeps unknown persons without kind/class filter", () => {
    const r = filterAndPage(punches, people, f, 1, 50, false);
    expect(r.rows.map((p) => p.personId)).toEqual(["9", "2", "3", "1"]);
    expect(r.total).toBe(4);
    expect(r.pageCount).toBe(1);
    expect(r.truncated).toBe(false);
  });
  it("filters by kind and excludes unknown persons", () => {
    const r = filterAndPage(punches, people, { ...f, kind: "student" }, 1, 50, false);
    expect(r.rows.map((p) => p.personId)).toEqual(["3", "1"]);
  });
  it("filters by class", () => {
    const r = filterAndPage(punches, people, { ...f, className: "A" }, 1, 50, false);
    expect(r.rows.map((p) => p.personId)).toEqual(["1"]);
  });
  it("paginates with boundaries and clamps page", () => {
    const many = Array.from({ length: 101 }, (_, i) =>
      punch("1", new Date(Date.UTC(2026, 0, 1, 0, 0, i)).toISOString()),
    );
    const p1 = filterAndPage(many, people, f, 1, 50, false);
    expect(p1.rows).toHaveLength(50);
    expect(p1.pageCount).toBe(3);
    expect(filterAndPage(many, people, f, 3, 50, false).rows).toHaveLength(1);
    expect(filterAndPage(many, people, f, 99, 50, false).rows).toHaveLength(1);
    expect(filterAndPage(many, people, f, 0, 50, false).rows).toHaveLength(50);
  });
  it("empty gives pageCount 1 and passes truncated flag", () => {
    const r = filterAndPage([], people, f, 1, 50, true);
    expect(r.pageCount).toBe(1);
    expect(r.truncated).toBe(true);
  });
});

describe("summarizeToday", () => {
  const today = "2026-01-05";
  const list: Array<Person & { id: string }> = [
    { ...person(), id: "1" },
    { ...person(), id: "2" },
    { ...person({ active: false }), id: "3" },
    { ...person(), id: "4" },
  ];
  const ids = (xs: Array<{ id: string }>) => xs.map((x) => x.id).sort();

  it("classifies present, late, absent; inactive excluded; unknown ignored; multiple punches once", () => {
    const punches = [
      punch("1", "2026-01-05T01:00:00Z"),
      punch("1", "2026-01-05T09:00:00Z", { direction: "out" }),
      punch("4", "2026-01-05T02:00:00Z", { late: true }),
      punch("3", "2026-01-05T02:00:00Z"),
      punch("999", "2026-01-05T02:00:00Z"),
    ];
    const r = summarizeToday(list, punches, [], today);
    expect(ids(r.present)).toEqual(["1", "4"]);
    expect(ids(r.late)).toEqual(["4"]);
    expect(ids(r.absent)).toEqual(["2"]);
  });
  it("nobody absent on a holiday", () => {
    const r = summarizeToday(list, [], [today], today);
    expect(r.absent).toEqual([]);
    expect(r.present).toEqual([]);
  });
  it("ignores punches from other dates", () => {
    const r = summarizeToday(list, [punch("1", "2026-01-04T01:00:00Z")], [], today);
    expect(ids(r.absent)).toEqual(["1", "2", "4"]);
  });
});
