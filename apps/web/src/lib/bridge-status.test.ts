import { describe, expect, it } from "vitest";
import { BRIDGE_OFFLINE_AFTER_SEC, bridgeHealth, formatSince } from "./bridge-status";

const now = new Date("2026-03-10T10:00:00Z");
const ago = (s: number) => new Date(now.getTime() - s * 1000);

describe("bridgeHealth", () => {
  it("is online when fresh and device online", () => {
    expect(bridgeHealth({ heartbeat: ago(10), deviceOnline: true }, now)).toEqual({ state: "online" });
  });
  it("is device-offline when fresh and device offline", () => {
    expect(bridgeHealth({ heartbeat: ago(10), deviceOnline: false }, now)).toEqual({ state: "device-offline" });
  });
  it("treats exactly 90 s as fresh", () => {
    expect(BRIDGE_OFFLINE_AFTER_SEC).toBe(90);
    expect(bridgeHealth({ heartbeat: ago(90), deviceOnline: true }, now).state).toBe("online");
  });
  it("is bridge-offline at 91 s with since", () => {
    const hb = ago(91);
    expect(bridgeHealth({ heartbeat: hb, deviceOnline: true }, now)).toEqual({ state: "bridge-offline", since: hb });
  });
  it("is bridge-offline without since when status is null", () => {
    expect(bridgeHealth(null, now)).toEqual({ state: "bridge-offline" });
  });
});

describe("formatSince", () => {
  it("formats just now, minutes, hours, days", () => {
    expect(formatSince(ago(20), now)).toBe("just now");
    expect(formatSince(ago(120), now)).toBe("2 min ago");
    expect(formatSince(ago(3 * 3600 + 60), now)).toBe("3 h ago");
    expect(formatSince(ago(2 * 86400), now)).toBe("2 d ago");
  });
  it("treats a future date as just now", () => {
    expect(formatSince(new Date(now.getTime() + 5000), now)).toBe("just now");
  });
});
