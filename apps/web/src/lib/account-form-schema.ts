import { ROLES } from "@hrm/shared";
import { z } from "zod";
import { MIN_PASSWORD_LENGTH } from "./accounts";

const password = z.string().min(MIN_PASSWORD_LENGTH, `Password must be at least ${MIN_PASSWORD_LENGTH} characters`);

/** Role/person rules shared by the create and change-role forms. */
function rolePerson<T extends { role: (typeof ROLES)[number]; personId: string }>(v: T, ctx: z.RefinementCtx) {
  if (v.role === "staff" && !v.personId) {
    ctx.addIssue({ code: "custom", path: ["personId"], message: "Select the person this staff account belongs to" });
  }
  if (v.role === "guardian" && v.personId) {
    ctx.addIssue({
      code: "custom",
      path: ["personId"],
      message: "Guardians are linked to students from the person page",
    });
  }
}

/** Guardians never carry a person; a stale value from a hidden picker is dropped, not rejected. */
function dropGuardianPerson<T extends { role: (typeof ROLES)[number]; personId: string }>(v: T): T {
  return v.role === "guardian" ? { ...v, personId: "" } : v;
}

export const createAccountFormSchema = z
  .object({
    email: z.string().trim().toLowerCase().pipe(z.email("Enter a valid email")),
    password,
    displayName: z.string().trim().max(200),
    role: z.enum(ROLES),
    personId: z.string(),
  })
  .transform(dropGuardianPerson)
  .superRefine(rolePerson);
export type CreateAccountFormValues = z.input<typeof createAccountFormSchema>;

export const changeRoleFormSchema = z
  .object({ role: z.enum(ROLES), personId: z.string() })
  .transform(dropGuardianPerson)
  .superRefine(rolePerson);
export type ChangeRoleFormValues = z.input<typeof changeRoleFormSchema>;

export const resetPasswordFormSchema = z.object({ password });
export type ResetPasswordFormValues = z.infer<typeof resetPasswordFormSchema>;
