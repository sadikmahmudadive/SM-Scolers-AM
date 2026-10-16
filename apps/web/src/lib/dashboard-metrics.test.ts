import { describe, expect, it } from "vitest";
import type { Attendance } from "@hrm/shared";
import { computeKpis, latestPunches } from "./dashboard-metrics";

const punch = (personId: string, late: boolean, ts = "2026-03-10T03:00:00Z"): Attendance => ({
  personId,
  ts: new Date(ts),
  date: "2026-03-10",
  status: "ok",
  direction: "in",
  deviceId: "d",
  late,
  earlyLeave: false,
});

describe("computeKpis", () => {
  const people = [
    { id: "a", active: true },
    { id: "b", active: true },
    { id: "c", active: false },
  ];
  it("excludes inactive people from totalPeople", () => {
    expect(computeKpis(people, [], []).totalPeople).toBe(2);
  });
  it("counts present and late once per person", () => {
    const k = computeKpis(people, [punch("a", true), punch("a", true), punch("b", false)], []);
    expect(k.present).toBe(2);
    expect(k.late).toBe(1);
  });
  it("counts only sent sms", () => {
    const k = computeKpis(people, [], [{ status: "sent" }, { status: "failed" }, { status: "skipped-stale" }, { status: "sent" }]);
    expect(k.smsSent).toBe(2);
  });
});

describe("latestPunches", () => {
  const items = [
    { id: 1, ts: new Date("2026-03-10T01:00:00Z") },
    { id: 2, ts: new Date("2026-03-10T03:00:00Z") },
    { id: 3, ts: new Date("2026-03-10T02:00:00Z") },
    { id: 4, ts: new Date("2026-03-10T03:00:00Z") },
  ];
  it("returns newest first, stable, bounded", () => {
    expect(latestPunches(items, 3).map((x) => x.id)).toEqual([2, 4, 3]);
  });
  it("does not mutate input and handles n > length", () => {
    const copy = [...items];
    expect(latestPunches(items, 10)).toHaveLength(4);
    expect(items).toEqual(copy);
  });
});
