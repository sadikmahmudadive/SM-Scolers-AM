import "server-only";
import { COLLECTIONS, type Attendance, type Person } from "@hrm/shared";
import { applySpec, logsQuerySpec, QUERY_LIMIT, type LogFilters } from "./attendance-queries";
import { getAdminDb } from "./firebase-admin";
import { DEFAULT_TIME_ZONE } from "./org-time";

export type PersonWithId = Person & { id: string };

function toDate(v: unknown): Date {
  if (v instanceof Date) return v;
  if (v && typeof (v as { toDate?: unknown }).toDate === "function") return (v as { toDate: () => Date }).toDate();
  return new Date(0);
}

export function toPerson(id: string, x: FirebaseFirestore.DocumentData): PersonWithId {
  return {
    id,
    name: String(x.name ?? ""),
    kind: x.kind,
    phone: x.phone || undefined,
    className: x.className || undefined,
    section: x.section || undefined,
    guardianUids: Array.isArray(x.guardianUids) ? x.guardianUids : [],
    deviceEnrolled: x.deviceEnrolled === true,
    active: x.active !== false,
    createdAt: toDate(x.createdAt),
  };
}

export function toAttendance(x: FirebaseFirestore.DocumentData): Attendance {
  return {
    personId: String(x.personId ?? ""),
    ts: toDate(x.ts),
    date: String(x.date ?? ""),
    status: String(x.status ?? ""),
    direction: x.direction === "out" ? "out" : "in",
    deviceId: String(x.deviceId ?? ""),
    late: x.late === true,
    earlyLeave: x.earlyLeave === true,
  };
}

export async function loadPeopleWithIds(): Promise<PersonWithId[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.people).get();
  return snap.docs.map((d) => toPerson(d.id, d.data()));
}

export async function loadTimeZone(): Promise<string> {
  const snap = await getAdminDb().collection(COLLECTIONS.settings).doc("app").get();
  const tz = snap.data()?.timeZone;
  return typeof tz === "string" && tz ? tz : DEFAULT_TIME_ZONE;
}

export async function loadHolidays(): Promise<string[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.holidays).get();
  return snap.docs.map((d) => d.id);
}

export async function loadLogs(filters: LogFilters): Promise<{
  people: Map<string, Person>;
  punches: Attendance[];
  truncated: boolean;
}> {
  const spec = logsQuerySpec(filters);
  const [snap, people] = await Promise.all([
    // Fetch one extra row so exactly QUERY_LIMIT rows is not reported as truncated.
    applySpec(getAdminDb().collection(COLLECTIONS.attendance), { ...spec, limit: spec.limit + 1 }).get(),
    loadPeopleWithIds(),
  ]);
  return {
    people: new Map(people.map((p) => [p.id, p])),
    punches: snap.docs.slice(0, QUERY_LIMIT).map((d) => toAttendance(d.data())),
    truncated: snap.size > QUERY_LIMIT,
  };
}
