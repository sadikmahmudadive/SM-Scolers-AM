import { describe, expect, it, vi } from "vitest";
import { exportAttendanceCsvWith } from "./attendance-export";

const filters = { from: "2026-01-01", to: "2026-01-01" };

describe("exportAttendanceCsvWith", () => {
  it("rejects non-admins without touching the db", async () => {
    const load = vi.fn();
    const timeZone = vi.fn();
    for (const caller of [null, { uid: "u", role: "manager" as const }, { uid: "u", role: "staff" as const }]) {
      await expect(exportAttendanceCsvWith({ load, timeZone }, caller, filters)).rejects.toThrow(/admin/i);
    }
    expect(load).not.toHaveBeenCalled();
    expect(timeZone).not.toHaveBeenCalled();
  });

  it("exports header and escaped rows filtered by kind", async () => {
    const people = new Map([
      ["1", { name: '=Evil, "Q"', kind: "student", className: "A", active: true }],
      ["2", { name: "T", kind: "teacher", active: true }],
    ]) as never;
    const mk = (personId: string, late: boolean) => ({
      personId,
      ts: new Date("2026-01-01T03:00:00Z"),
      date: "2026-01-01",
      status: "present",
      direction: "in",
      deviceId: "d",
      late,
      earlyLeave: false,
    });
    const load = vi.fn(async () => ({ people, punches: [mk("1", true), mk("2", false)] as never, truncated: false }));
    const csv = await exportAttendanceCsvWith(
      { load, timeZone: async () => "Asia/Dhaka" },
      { uid: "a", role: "admin" },
      { ...filters, kind: "student" },
    );
    const lines = csv.trimEnd().split("\r\n");
    expect(lines[0]).toBe("date,time,personId,name,kind,className,direction,late,earlyLeave,status,deviceId");
    expect(lines).toHaveLength(2);
    expect(lines[1]).toBe('2026-01-01,09:00,1,"\'=Evil, ""Q""",student,A,in,true,false,present,d');
  });
});
