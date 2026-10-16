import { z } from "zod";
import { PERSON_ID_PATTERN, PERSON_KINDS } from "./csv";

export const personFormSchema = z.object({
  id: z.string().regex(PERSON_ID_PATTERN, "Letters and digits only (no spaces or /)"),
  name: z.string().trim().min(1, "Name is required"),
  kind: z.enum(PERSON_KINDS),
  phone: z.string(),
  fatherPhone: z.string(),
  motherPhone: z.string(),
  className: z.string(),
  section: z.string(),
  departmentId: z.string(),
  managerId: z.string(),
  active: z.boolean(),
});
export type PersonFormValues = z.infer<typeof personFormSchema>;
