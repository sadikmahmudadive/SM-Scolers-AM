import { describe, expect, it, vi } from "vitest";
import { exportStatsCsvWith } from "./stats-export";

describe("exportStatsCsvWith", () => {
  it("rejects non-admins without touching the db", async () => {
    const load = vi.fn();
    for (const c of [null, { uid: "u", role: "manager" as const }, { uid: "u", role: "staff" as const }]) {
      await expect(exportStatsCsvWith({ load }, c, { from: "2026-01-01", to: "2026-01-02" })).rejects.toThrow(/admin/i);
    }
    expect(load).not.toHaveBeenCalled();
  });
  it("rejects invalid input", async () => {
    const load = vi.fn();
    await expect(exportStatsCsvWith({ load }, { uid: "a", role: "admin" }, { from: "x", to: "y" })).rejects.toThrow();
    expect(load).not.toHaveBeenCalled();
  });
  it("exports daily rows", async () => {
    const load = vi.fn().mockResolvedValue({
      punches: [
        { personId: "1", ts: new Date(), date: "2026-01-01", status: "p", direction: "in", deviceId: "d", late: true, earlyLeave: false },
      ],
      people: [{ id: "1", active: true }],
      holidays: [],
      truncated: true,
    });
    const r = await exportStatsCsvWith({ load }, { uid: "a", role: "admin" }, { from: "2026-01-01", to: "2026-01-02" });
    expect(r.truncated).toBe(true);
    expect(r.csv.split("\r\n")[0]).toBe("date,present,absent,late,punches,noData");
    expect(r.csv).toContain("2026-01-01,1,0,1,1,false");
    expect(r.csv).toContain("2026-01-02,0,0,0,0,true");
  });
});
