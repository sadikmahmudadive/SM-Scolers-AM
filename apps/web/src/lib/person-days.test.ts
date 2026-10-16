import type { Attendance } from "@hrm/shared";
import { describe, expect, it } from "vitest";
import { buildDayRows, lastNDays, todayStatus } from "./person-days";

function punch(date: string, iso: string, direction: "in" | "out", extra: Partial<Attendance> = {}): Attendance {
  return {
    personId: "p1",
    ts: new Date(iso),
    date,
    status: "ok",
    direction,
    deviceId: "d",
    late: false,
    earlyLeave: false,
    ...extra,
  };
}

describe("buildDayRows", () => {
  const range = { from: "2026-03-01", to: "2026-03-03" };
  it("includes every date in range inclusive, newest first, no-punch days included", () => {
    const rows = buildDayRows([], range, []);
    expect(rows.map((r) => r.date)).toEqual(["2026-03-03", "2026-03-02", "2026-03-01"]);
    expect(rows[0]).toMatchObject({ punches: 0, late: false, earlyLeave: false, holiday: false });
    expect(rows[0].firstIn).toBeUndefined();
  });
  it("flags holidays", () => {
    const rows = buildDayRows([], range, ["2026-03-02"]);
    expect(rows.find((r) => r.date === "2026-03-02")?.holiday).toBe(true);
    expect(rows.find((r) => r.date === "2026-03-01")?.holiday).toBe(false);
  });
  it("computes first in / last out in the org zone and aggregates flags", () => {
    // Asia/Dhaka is UTC+6
    const rows = buildDayRows(
      [
        punch("2026-03-02", "2026-03-02T03:00:00Z", "in", { late: true }),
        punch("2026-03-02", "2026-03-02T02:00:00Z", "in"),
        punch("2026-03-02", "2026-03-02T09:00:00Z", "out"),
        punch("2026-03-02", "2026-03-02T10:00:00Z", "out", { earlyLeave: true }),
      ],
      range,
      [],
      "Asia/Dhaka",
    );
    const r = rows.find((x) => x.date === "2026-03-02")!;
    expect(r).toMatchObject({ firstIn: "08:00", lastOut: "16:00", punches: 4, late: true, earlyLeave: true });
  });
  it("ignores punches outside the range", () => {
    const rows = buildDayRows([punch("2026-02-28", "2026-02-28T02:00:00Z", "in")], range, []);
    expect(rows).toHaveLength(3);
    expect(rows.every((r) => r.punches === 0)).toBe(true);
  });
});

describe("todayStatus", () => {
  const today = "2026-03-02";
  it("absent without punches", () => expect(todayStatus([], today, false)).toBe("absent"));
  it("holiday without punches on a holiday", () => expect(todayStatus([], today, true)).toBe("holiday"));
  it("present with a punch", () =>
    expect(todayStatus([punch(today, "2026-03-02T02:00:00Z", "in")], today, false)).toBe("present"));
  it("late when any punch today is late", () =>
    expect(todayStatus([punch(today, "2026-03-02T04:00:00Z", "in", { late: true })], today, false)).toBe("late"));
  it("ignores other days", () =>
    expect(todayStatus([punch("2026-03-01", "2026-03-01T02:00:00Z", "in")], today, false)).toBe("absent"));
  it("punch on a holiday still counts as present", () =>
    expect(todayStatus([punch(today, "2026-03-02T02:00:00Z", "in")], today, true)).toBe("present"));
});

describe("lastNDays", () => {
  it("is inclusive of today", () => {
    expect(lastNDays("2026-03-14", 14)).toEqual({ from: "2026-03-01", to: "2026-03-14" });
    expect(lastNDays("2026-03-02", 1)).toEqual({ from: "2026-03-02", to: "2026-03-02" });
  });
});
