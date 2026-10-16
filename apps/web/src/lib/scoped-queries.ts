export type ScopedOp = ">=" | "<=" | "==" | "array-contains";
export type ScopedSpec = {
  collection: "people" | "attendance";
  where: Array<[field: string, op: ScopedOp, value: string]>;
  orderBy?: [field: string, direction: "asc" | "desc"];
  limit: number;
};

export const TEAM_LIMIT = 60;
export const CHILDREN_LIMIT = 20;
export const PERSON_ATTENDANCE_LIMIT = 500;

/** People managed by `uid`. The uid must come from the verified session, never from URL input. */
export function teamPeopleSpec(uid: string): ScopedSpec {
  return { collection: "people", where: [["managerId", "==", uid]], limit: TEAM_LIMIT };
}

/** Students linked to the guardian `uid`. */
export function childrenSpec(uid: string): ScopedSpec {
  return { collection: "people", where: [["guardianUids", "array-contains", uid]], limit: CHILDREN_LIMIT };
}

/** One person's punches in a range; uses the (personId asc, date desc) composite index. */
export function personAttendanceSpec(personId: string, range: { from: string; to: string }): ScopedSpec {
  return {
    collection: "attendance",
    where: [
      ["personId", "==", personId],
      ["date", ">=", range.from],
      ["date", "<=", range.to],
    ],
    orderBy: ["date", "desc"],
    limit: PERSON_ATTENDANCE_LIMIT,
  };
}

/** Structural subset of an Admin SDK Query/Firestore so this module stays pure. */
type Queryable<Q> = {
  where(field: string, op: ScopedOp, value: string): Q;
  orderBy(field: string, direction: "asc" | "desc"): Q;
  limit(n: number): Q;
};

export function applyScopedSpec<Q extends Queryable<Q>>(
  db: { collection(name: string): Queryable<Q> },
  spec: ScopedSpec,
): Q {
  let q: Queryable<Q> = db.collection(spec.collection);
  for (const [field, op, value] of spec.where) q = q.where(field, op, value);
  if (spec.orderBy) q = q.orderBy(spec.orderBy[0], spec.orderBy[1]);
  return q.limit(spec.limit);
}

/** IDOR guard: the requested id only if it is in the allowed set, else the first allowed id (or null). */
export function resolveSelection(requestedId: string | undefined, allowedIds: readonly string[]): string | null {
  if (requestedId !== undefined && allowedIds.includes(requestedId)) return requestedId;
  return allowedIds[0] ?? null;
}
