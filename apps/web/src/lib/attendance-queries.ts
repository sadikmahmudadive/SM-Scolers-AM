import type { Attendance, Person } from "@hrm/shared";
import type { PersonKind } from "./csv";

export type LogFilters = {
  from: string;
  to: string;
  personId?: string;
  kind?: PersonKind;
  className?: string;
};

export type QueryOp = ">=" | "<=" | "==";
export type QuerySpec = {
  where: Array<[field: string, op: QueryOp, value: string]>;
  orderBy: [field: string, direction: "asc" | "desc"];
  limit: number;
};

export const QUERY_LIMIT = 5000;
export const LOG_PAGE_SIZE = 50;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Index use (firebase/firestore.indexes.json): date range + orderBy date is a single-field
 * (automatic) index; adding personId equality needs (personId asc, date desc). Newest-first
 * so the limit keeps the most recent rows; exact ts ordering and kind/class filtering happen in memory.
 */
export function logsQuerySpec(filters: LogFilters): QuerySpec {
  if (!DATE_RE.test(filters.from) || !DATE_RE.test(filters.to)) {
    throw new Error("Dates must be yyyy-MM-dd");
  }
  if (filters.from > filters.to) throw new Error("From date must not be after To date");
  const where: QuerySpec["where"] = [];
  if (filters.personId) where.push(["personId", "==", filters.personId]);
  where.push(["date", ">=", filters.from], ["date", "<=", filters.to]);
  return { where, orderBy: ["date", "desc"], limit: QUERY_LIMIT };
}

/** Structural subset of an Admin SDK Query so this module stays pure. */
type Queryable<Q> = {
  where(field: string, op: QueryOp, value: string): Q;
  orderBy(field: string, direction: "asc" | "desc"): Q;
  limit(n: number): Q;
};

export function applySpec<Q extends Queryable<Q>>(collection: Queryable<Q>, spec: QuerySpec): Q {
  let q: Queryable<Q> = collection;
  for (const [field, op, value] of spec.where) q = q.where(field, op, value);
  return q.orderBy(spec.orderBy[0], spec.orderBy[1]).limit(spec.limit);
}

export type PagedLogs = { rows: Attendance[]; total: number; page: number; pageCount: number; truncated: boolean };

export function filterAndPage(
  punches: readonly Attendance[],
  people: ReadonlyMap<string, Pick<Person, "kind" | "className">>,
  filters: LogFilters,
  page: number,
  pageSize = LOG_PAGE_SIZE,
  truncated = false,
): PagedLogs {
  const needsPerson = Boolean(filters.kind || filters.className);
  const filtered = punches.filter((p) => {
    if (!needsPerson) return true;
    const person = people.get(p.personId);
    if (!person) return false;
    if (filters.kind && person.kind !== filters.kind) return false;
    if (filters.className && person.className !== filters.className) return false;
    return true;
  });
  const sorted = [...filtered].sort((a, b) => b.ts.getTime() - a.ts.getTime());
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const requested = Number.isFinite(page) ? Math.floor(page) : 1;
  const current = requested >= 1 && requested <= pageCount ? requested : requested > pageCount ? pageCount : 1;
  return {
    rows: sorted.slice((current - 1) * pageSize, current * pageSize),
    total: sorted.length,
    page: current,
    pageCount,
    truncated,
  };
}

export function summarizeToday<P extends Pick<Person, "active"> & { id: string }>(
  people: readonly P[],
  punches: readonly Pick<Attendance, "personId" | "date" | "late">[],
  holidays: readonly string[],
  today: string,
): { present: P[]; absent: P[]; late: P[] } {
  const punched = new Set<string>();
  const lateIds = new Set<string>();
  for (const p of punches) {
    if (p.date !== today) continue;
    punched.add(p.personId);
    if (p.late) lateIds.add(p.personId);
  }
  const active = people.filter((p) => p.active);
  const present = active.filter((p) => punched.has(p.id));
  const late = present.filter((p) => lateIds.has(p.id));
  const absent = holidays.includes(today) ? [] : active.filter((p) => !punched.has(p.id));
  return { present, absent, late };
}
