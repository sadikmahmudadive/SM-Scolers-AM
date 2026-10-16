import "server-only";
import { COLLECTIONS, type Attendance } from "@hrm/shared";
import type { Session } from "./access";
import { toAttendance, toPerson, type PersonWithId } from "./attendance-loader";
import { getAdminDb } from "./firebase-admin";
import {
  applyScopedSpec,
  childrenSpec,
  personAttendanceSpec,
  resolveSelection,
  teamPeopleSpec,
  type ScopedSpec,
} from "./scoped-queries";

export type ScopedDeps = {
  queryPeople: (spec: ScopedSpec) => Promise<PersonWithId[]>;
  getPerson: (id: string) => Promise<PersonWithId | null>;
  queryPunches: (spec: ScopedSpec) => Promise<Attendance[]>;
};

export function adminScopedDeps(): ScopedDeps {
  return {
    queryPeople: async (spec) => {
      const snap = await applyScopedSpec(getAdminDb(), spec).get();
      return snap.docs.map((d) => toPerson(d.id, d.data()));
    },
    getPerson: async (id) => {
      const snap = await getAdminDb().collection(COLLECTIONS.people).doc(id).get();
      return snap.exists ? toPerson(snap.id, snap.data() ?? {}) : null;
    },
    queryPunches: async (spec) => {
      const snap = await applyScopedSpec(getAdminDb(), spec).get();
      return snap.docs.map((d) => toAttendance(d.data()));
    },
  };
}

type Identity = Pick<Session, "uid" | "personId" | "role">;

/** People whose managerId is the verified session uid. No role-based broadening, admins included. */
export async function loadTeam(
  session: Identity,
  deps: ScopedDeps,
): Promise<{ reports: PersonWithId[]; truncated: boolean }> {
  const spec = teamPeopleSpec(session.uid);
  const reports = await deps.queryPeople(spec);
  return { reports, truncated: reports.length >= spec.limit };
}

export async function loadChildren(
  session: Identity,
  deps: ScopedDeps,
): Promise<{ children: PersonWithId[]; truncated: boolean }> {
  const spec = childrenSpec(session.uid);
  const children = await deps.queryPeople(spec);
  return { children, truncated: children.length >= spec.limit };
}

export async function loadSelf(
  session: Identity,
  deps: ScopedDeps,
): Promise<{ linked: false } | { linked: true; person: PersonWithId }> {
  if (!session.personId) return { linked: false };
  const person = await deps.getPerson(session.personId);
  return person ? { linked: true, person } : { linked: false };
}

export function loadPersonDays(
  personId: string,
  range: { from: string; to: string },
  deps: ScopedDeps,
): Promise<Attendance[]> {
  return deps.queryPunches(personAttendanceSpec(personId, range));
}

/** Resolves the requested id against the scoped set first; attendance is only read for an allowed id. */
export async function loadSelectedDays(
  requestedId: string | undefined,
  allowedIds: readonly string[],
  range: { from: string; to: string },
  deps: ScopedDeps,
): Promise<{ personId: string; punches: Attendance[] } | null> {
  const personId = resolveSelection(requestedId, allowedIds);
  if (personId === null) return null;
  return { personId, punches: await loadPersonDays(personId, range, deps) };
}

/** Punches for one day per person, for ids already inside the scoped set. */
export async function loadTodayPunches(
  allowedIds: readonly string[],
  today: string,
  deps: ScopedDeps,
): Promise<Map<string, Attendance[]>> {
  const range = { from: today, to: today };
  const entries = await Promise.all(allowedIds.map(async (id) => [id, await loadPersonDays(id, range, deps)] as const));
  return new Map(entries);
}
