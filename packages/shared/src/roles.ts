export const ROLES = ["admin", "manager", "staff", "guardian"] as const;
export type Role = (typeof ROLES)[number];
