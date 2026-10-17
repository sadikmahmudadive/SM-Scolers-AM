import { describe, expect, it } from "vitest";
import type { Attendance } from "@hrm/shared";
import {
  PERSON_REPORT_PUNCH_CAP,
  authorizeReportAccess,
  buildPersonReport,
  decideReportResponse,
  isSchoolDay,
  reportParamsSchema,
} from "./person-report";

const mk = (personId: string, iso: string, o: Partial<Attendance> = {}): Attendance => ({
  personId,
  ts: new Date(iso),
  date: iso.slice(0, 10),
  status: "present",
  direction: "in",
  deviceId: "d",
  late: false,
  earlyLeave: false,
  ...o,
});
const person = { id: "7", name: "A", kind: "student" as const, managerId: "m1" };
// 2026-01-05 is a Monday; 2026-01-09 Friday, 2026-01-10 Saturday, 2026-01-11 Sunday.
const FRI_SAT = [5, 6];

describe("isSchoolDay", () => {
  it("excludes holidays and configured weekend days", () => {
    const holidays = new Set(["2026-01-07"]);
    expect(isSchoolDay("2026-01-05", holidays, FRI_SAT)).toBe(true); // Monday
    expect(isSchoolDay("2026-01-07", holidays, FRI_SAT)).toBe(false); // holiday
    expect(isSchoolDay("2026-01-09", holidays, FRI_SAT)).toBe(false); // Friday
    expect(isSchoolDay("2026-01-10", holidays, FRI_SAT)).toBe(false); // Saturday
    expect(isSchoolDay("2026-01-11", holidays, FRI_SAT)).toBe(true); // Sunday
    expect(isSchoolDay("2026-01-11", holidays, [0])).toBe(false);
    expect(isSchoolDay("2026-01-10", holidays, [])).toBe(true);
  });
});

describe("buildPersonReport", () => {
  const range = { from: "2026-01-05", to: "2026-01-11" };
  // Only this person's punches: no org-wide data is needed any more.
  const mine = [
    mk("7", "2026-01-05T03:00:00Z", { late: true }),
    mk("7", "2026-01-05T09:00:00Z", { direction: "out", earlyLeave: true }),
    mk("7", "2026-01-08T03:00:00Z"),
    mk("7", "2026-01-10T04:00:00Z"), // came in on a Saturday
  ];
  const r = buildPersonReport(person, mine, range, ["2026-01-07"], FRI_SAT, "UTC", "2026-01-20");
  it("lists school days (absent when there is no punch) and closure days only with punches", () => {
    expect(r.days.map((d) => [d.date, d.absent])).toEqual([
      ["2026-01-05", false],
      ["2026-01-06", true], // a school day without a punch is an absence
      ["2026-01-08", false],
      ["2026-01-10", false], // weekend, but the person punched: shown, never absent
      ["2026-01-11", true],
    ]);
    expect(r.days[0]).toMatchObject({
      first: "03:00",
      last: "09:00",
      late: true,
      earlyLeave: true,
      punches: 2,
      directions: "in, out",
    });
    expect(r.days[1]).toMatchObject({ punches: 0, first: null, last: null });
  });
  it("summarises", () => {
    expect(r.summary).toEqual({ present: 3, late: 1, earlyLeave: 1, punches: 4, absent: 2 });
  });
  it("ignores punches of other people", () => {
    const other = buildPersonReport(person, [mk("8", "2026-01-06T03:00:00Z")], range, [], FRI_SAT, "UTC", "2026-01-20");
    expect(other.summary.present).toBe(0);
  });
  it("never marks days after today as absent", () => {
    const partial = buildPersonReport(person, [], range, [], FRI_SAT, "UTC", "2026-01-06");
    expect(partial.days.map((d) => d.date)).toEqual(["2026-01-05", "2026-01-06"]);
  });
});

describe("authorizeReportAccess", () => {
  it("decides", () => {
    expect(authorizeReportAccess({ uid: "a", role: "admin" }, person)).toBe("ok");
    expect(authorizeReportAccess({ uid: "m1", role: "manager" }, person)).toBe("ok");
    expect(authorizeReportAccess({ uid: "m2", role: "manager" }, person)).toBe("forbidden");
    expect(authorizeReportAccess({ uid: "m1", role: "staff" }, person)).toBe("forbidden");
    expect(authorizeReportAccess(null, person)).toBe("unauthorized");
    expect(authorizeReportAccess({ uid: "a", role: "admin" }, null)).toBe("not-found");
    expect(authorizeReportAccess({ uid: "m1", role: "manager" }, { ...person, managerId: undefined })).toBe("forbidden");
  });
});

describe("reportParamsSchema", () => {
  it("validates id and dates", () => {
    expect(reportParamsSchema.safeParse({ id: "abc1", from: "2026-01-01", to: "2026-01-02" }).success).toBe(true);
    expect(reportParamsSchema.safeParse({ id: "a/b", from: "2026-01-01", to: "2026-01-02" }).success).toBe(false);
    expect(reportParamsSchema.safeParse({ id: "1", from: "2026-01-03", to: "2026-01-02" }).success).toBe(false);
    expect(reportParamsSchema.safeParse({ id: "1", from: "x", to: "2026-01-02" }).success).toBe(false);
  });
});

describe("decideReportResponse", () => {
  it("413 when the per-person cap truncated the load, 200 otherwise", () => {
    expect(PERSON_REPORT_PUNCH_CAP).toBe(5000);
    expect(decideReportResponse({ truncated: true })).toEqual({
      status: 413,
      error: "This person has more than 5000 punches in the range - choose a narrower date range",
    });
    expect(decideReportResponse({ truncated: false })).toEqual({ status: 200 });
  });
});
