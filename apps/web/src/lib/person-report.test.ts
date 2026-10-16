import { describe, expect, it } from "vitest";
import type { Attendance } from "@hrm/shared";
import { authorizeReportAccess, buildPersonReport, reportParamsSchema } from "./person-report";

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

describe("buildPersonReport", () => {
  const range = { from: "2026-01-05", to: "2026-01-09" };
  const all = [
    mk("7", "2026-01-05T03:00:00Z", { late: true }),
    mk("7", "2026-01-05T09:00:00Z", { direction: "out", earlyLeave: true }),
    mk("8", "2026-01-06T03:00:00Z"),
    mk("7", "2026-01-08T03:00:00Z"),
    mk("8", "2026-01-08T03:00:00Z"),
    mk("8", "2026-01-09T03:00:00Z"),
  ];
  const r = buildPersonReport(person, all, range, ["2026-01-09"], "UTC");
  it("builds days with first/last and flags, excluding noData and holidays", () => {
    expect(r.days.map((d) => d.date)).toEqual(["2026-01-05", "2026-01-06", "2026-01-08"]);
    expect(r.days[0]).toMatchObject({
      first: "03:00",
      last: "09:00",
      late: true,
      earlyLeave: true,
      punches: 2,
      absent: false,
      directions: "in, out",
    });
    expect(r.days[1]).toMatchObject({ absent: true, punches: 0, first: null, last: null });
  });
  it("summarises", () => {
    expect(r.summary).toEqual({ present: 2, late: 1, earlyLeave: 1, punches: 3, absent: 1 });
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
