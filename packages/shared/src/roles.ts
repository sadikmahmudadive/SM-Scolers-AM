export const ROLES = ["admin", "manager", "staff", "guardian"] as const;
export type Role = (typeof ROLES)[number];

export type Action = "manage" | "read:all" | "read:team" | "read:self" | "read:children";

const PERMISSIONS: Record<Role, readonly Action[]> = {
  admin: ["manage", "read:all", "read:team", "read:self", "read:children"],
  manager: ["read:team", "read:self"],
  staff: ["read:self"],
  guardian: ["read:children"],
};

export function can(role: Role, action: Action): boolean {
  return PERMISSIONS[role].includes(action);
}
