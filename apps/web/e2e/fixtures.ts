// Shared constants for the E2E suite. All credentials are TEST values for the local emulators only.
export const PASSWORD = "E2e-Passw0rd!";
export const PROJECT_ID = "demo-hrm";
export const TIME_ZONE = "Asia/Dhaka";

export const USERS = {
  admin: { email: "admin@example.test", role: "admin", home: "/dashboard" },
  manager: { email: "manager@example.test", role: "manager", home: "/team" },
  staff: { email: "staff@example.test", role: "staff", home: "/me", personId: "101" },
  guardian: { email: "guardian@example.test", role: "guardian", home: "/children" },
  norole: { email: "norole@example.test", role: null, home: null },
} as const;
export type Who = keyof typeof USERS;

export const PEOPLE = {
  rahim: { id: "100", name: "Rahim Uddin" },
  staffSelf: { id: "101", name: "Staff Self" },
  ayesha: { id: "201", name: "Ayesha Rahman" },
  other: { id: "202", name: "Other Child" },
} as const;

/** Org-local (Asia/Dhaka) yyyy-MM-dd for `now`, shifted by `offsetDays`. */
export function dhakaDate(offsetDays = 0, now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + offsetDays * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(shifted);
}

/** The instant for org-local `date` at `hh:mm` (Asia/Dhaka is UTC+6, no DST). */
export function dhakaInstant(date: string, hhmm: string): Date {
  return new Date(`${date}T${hhmm}:00+06:00`);
}

export function punchDocId(personId: string, date: string, hhmm: string): string {
  return `${personId}_${date.replace(/\D/g, "")}${hhmm.replace(":", "")}00`;
}
