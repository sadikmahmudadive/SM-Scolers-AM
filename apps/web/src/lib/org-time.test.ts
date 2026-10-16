import { describe, expect, it } from "vitest";
import { formatTimeInZone, todayInZone } from "./org-time";

describe("todayInZone", () => {
  const now = new Date("2026-03-10T20:30:00Z"); // 02:30 on the 11th in Dhaka (UTC+6)
  it("crosses midnight for Asia/Dhaka", () => {
    expect(todayInZone("Asia/Dhaka", now)).toBe("2026-03-11");
    expect(todayInZone("UTC", now)).toBe("2026-03-10");
  });
  it("falls back to the default zone on an invalid zone", () => {
    expect(todayInZone("Not/AZone", now)).toBe("2026-03-11");
  });
});

describe("formatTimeInZone", () => {
  it("formats HH:mm in zone", () => {
    expect(formatTimeInZone("Asia/Dhaka", new Date("2026-03-10T20:30:00Z"))).toBe("02:30");
    expect(formatTimeInZone("UTC", new Date("2026-03-10T20:30:00Z"))).toBe("20:30");
  });
});
