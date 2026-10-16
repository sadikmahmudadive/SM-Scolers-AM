import { describe, expect, it } from "vitest";
import { changeRoleFormSchema, createAccountFormSchema } from "./account-form-schema";

const base = { email: " A@B.co ", password: "correct-horse-battery", displayName: "", personId: "" };

describe("account form schemas", () => {
  it("drops a stale personId for guardians and submits cleanly", () => {
    const r = createAccountFormSchema.safeParse({ ...base, role: "guardian", personId: "P1" });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.personId).toBe("");
      expect(r.data.email).toBe("a@b.co");
    }
    const c = changeRoleFormSchema.safeParse({ role: "guardian", personId: "P1" });
    expect(c.success && c.data.personId).toBe("");
  });
  it("still rejects staff without a person", () => {
    expect(createAccountFormSchema.safeParse({ ...base, role: "staff" }).success).toBe(false);
    expect(changeRoleFormSchema.safeParse({ role: "staff", personId: "" }).success).toBe(false);
    expect(changeRoleFormSchema.safeParse({ role: "staff", personId: "P1" }).success).toBe(true);
  });
});
