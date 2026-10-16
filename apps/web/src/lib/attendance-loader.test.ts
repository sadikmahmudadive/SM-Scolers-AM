import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("./firebase-admin", () => ({ getAdminDb: vi.fn() }));

import { toPerson } from "./attendance-loader";

describe("toPerson", () => {
  it("maps phones, manager and department", () => {
    const p = toPerson("1", {
      name: "N",
      kind: "student",
      fatherPhone: "01",
      motherPhone: "02",
      managerId: "m",
      departmentId: "d",
    });
    expect(p).toMatchObject({ fatherPhone: "01", motherPhone: "02", managerId: "m", departmentId: "d" });
  });
  it("leaves empties undefined", () => {
    const p = toPerson("1", { name: "N", kind: "staff", managerId: "" });
    expect(p.managerId).toBeUndefined();
    expect(p.fatherPhone).toBeUndefined();
  });
});
