import { describe, expect, it, vi } from "vitest";
import { buildCommandDoc, enqueueCommandWith } from "./commands";

describe("buildCommandDoc", () => {
  it("builds a pending command", () => {
    const now = new Date("2026-01-01T00:00:00Z");
    expect(buildCommandDoc("sync_device_users", {}, "u1", now)).toEqual({
      type: "sync_device_users",
      payload: {},
      status: "pending",
      createdBy: "u1",
      createdAt: now,
    });
  });
  it("rejects an unknown type", () => {
    expect(() => buildCommandDoc("nope" as never, {}, "u", new Date())).toThrow();
  });
});

describe("enqueueCommandWith", () => {
  it("rejects a non-admin without writing", async () => {
    const add = vi.fn();
    const deps = { add, now: () => new Date() };
    await expect(enqueueCommandWith(deps, { uid: "u", role: "staff" }, "sync_device_users", {})).rejects.toThrow(/admin/);
    await expect(enqueueCommandWith(deps, null, "sync_device_users", {})).rejects.toThrow(/admin/);
    expect(add).not.toHaveBeenCalled();
  });
  it("writes and returns the id for an admin", async () => {
    const add = vi.fn().mockResolvedValue("cmd1");
    const id = await enqueueCommandWith({ add, now: () => new Date(0) }, { uid: "a", role: "admin" }, "ussd", {
      code: "*1#",
    });
    expect(id).toBe("cmd1");
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ type: "ussd", status: "pending", createdBy: "a" }));
  });
});
