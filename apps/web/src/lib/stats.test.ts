import { describe, expect, it } from "vitest";
import type { Attendance } from "@hrm/shared";
import { computeDailyStats, rangeFromPreset, summarizeStats, type DailyStat } from "./stats";

const punch = (personId: string, date: string, late = false): Attendance => ({
  personId,
  ts: new Date(`${date}T03:00:00Z`),
  date,
  status: "present",
  direction: "in",
  deviceId: "d",
  late,
  earlyLeave: false,
});
const people = [
  { id: "1", active: true },
  { id: "2", active: true },
  { id: "3", active: false },
];

describe("computeDailyStats", () => {
  it("counts distinct people but all punches", () => {
    const rows = computeDailyStats(
      [punch("1", "2026-01-05"), punch("1", "2026-01-05"), punch("2", "2026-01-05")],
      people,
      { from: "2026-01-05", to: "2026-01-05" },
      [],
    );
    expect(rows).toEqual([{ date: "2026-01-05", present: 2, absent: 0, late: 0, punches: 3, noData: false }]);
  });
  it("counts late distinctly and absent as active minus present", () => {
    const [r] = computeDailyStats(
      [punch("1", "2026-01-05", true), punch("1", "2026-01-05", true)],
      people,
      { from: "2026-01-05", to: "2026-01-05" },
      [],
    );
    expect(r).toMatchObject({ present: 1, late: 1, absent: 1, punches: 2 });
  });
  it("omits holidays and is inclusive", () => {
    const rows = computeDailyStats([punch("1", "2026-01-05")], people, { from: "2026-01-04", to: "2026-01-06" }, ["2026-01-06"]);
    expect(rows.map((r) => r.date)).toEqual(["2026-01-04", "2026-01-05"]);
  });
  it("marks zero-punch days noData with zeros", () => {
    const [r] = computeDailyStats([], people, { from: "2026-01-04", to: "2026-01-04" }, []);
    expect(r).toEqual({ date: "2026-01-04", present: 0, absent: 0, late: 0, punches: 0, noData: true });
  });
  it("excludes inactive and unknown people from present/late but counts punches", () => {
    const [r] = computeDailyStats(
      [punch("3", "2026-01-05", true), punch("99", "2026-01-05", true), punch("1", "2026-01-05")],
      people,
      { from: "2026-01-05", to: "2026-01-05" },
      [],
    );
    expect(r).toEqual({ date: "2026-01-05", present: 1, absent: 1, late: 0, punches: 3, noData: false });
  });
  it("a day with only inactive punches is not noData", () => {
    const [r] = computeDailyStats([punch("3", "2026-01-05")], people, { from: "2026-01-05", to: "2026-01-05" }, []);
    expect(r).toMatchObject({ noData: false, present: 0, absent: 2, punches: 1 });
  });
  it("throws when from > to", () => {
    expect(() => computeDailyStats([], people, { from: "2026-01-06", to: "2026-01-05" }, [])).toThrow();
  });
});

describe("rangeFromPreset", () => {
  it("7d and 30d", () => {
    expect(rangeFromPreset("7d", "2026-03-10")).toEqual({ from: "2026-03-04", to: "2026-03-10" });
    expect(rangeFromPreset("30d", "2026-03-10")).toEqual({ from: "2026-02-09", to: "2026-03-10" });
  });
  it("validates custom", () => {
    expect(rangeFromPreset("custom", "2026-03-10", { from: "2026-01-01", to: "2026-01-31" })).toEqual({
      from: "2026-01-01",
      to: "2026-01-31",
    });
    expect(() => rangeFromPreset("custom", "2026-03-10")).toThrow();
    expect(() => rangeFromPreset("custom", "2026-03-10", { from: "2026-02-01", to: "2026-01-01" })).toThrow();
    expect(() => rangeFromPreset("custom", "2026-03-10", { from: "bad", to: "2026-01-01" })).toThrow();
    expect(() => rangeFromPreset("custom", "2026-03-10", { from: "2026-02-30", to: "2026-03-01" })).toThrow();
  });
  it("max span 366 days inclusive", () => {
    expect(() => rangeFromPreset("custom", "2026-03-10", { from: "2025-01-01", to: "2026-01-01" })).not.toThrow();
    expect(() => rangeFromPreset("custom", "2026-03-10", { from: "2025-01-01", to: "2026-01-02" })).toThrow();
  });
});

describe("summarizeStats", () => {
  const row = (present: number, late: number, punches: number, noData = false): DailyStat => ({
    date: "d",
    present,
    absent: 0,
    late,
    punches,
    noData,
  });
  it("excludes noData from averages", () => {
    expect(summarizeStats([row(10, 2, 20), row(0, 0, 0, true), row(5, 1, 6)])).toEqual({
      avgPresent: 7.5,
      avgLate: 1.5,
      totalPunches: 26,
      days: 2,
    });
  });
  it("rounds to one decimal", () => {
    expect(summarizeStats([row(1, 0, 1), row(1, 0, 1), row(2, 1, 2)]).avgPresent).toBe(1.3);
  });
  it("is zero for empty", () => {
    expect(summarizeStats([])).toEqual({ avgPresent: 0, avgLate: 0, totalPunches: 0, days: 0 });
  });
});
