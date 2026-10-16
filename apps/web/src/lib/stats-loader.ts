import "server-only";
import { COLLECTIONS } from "@hrm/shared";
import { applySpec, type QuerySpec } from "./attendance-queries";
import { loadHolidays, loadPeopleWithIds, toAttendance } from "./attendance-loader";
import { getAdminDb } from "./firebase-admin";
import type { StatsData } from "./stats-export";

export const STATS_QUERY_LIMIT = 50_000;

/** Date-range only (single-field automatic index), newest first so a cap keeps the latest days. */
export function statsQuerySpec(range: { from: string; to: string }): QuerySpec {
  return {
    where: [
      ["date", ">=", range.from],
      ["date", "<=", range.to],
    ],
    orderBy: ["date", "desc"],
    limit: STATS_QUERY_LIMIT,
  };
}

export async function loadStatsData(range: { from: string; to: string }): Promise<StatsData> {
  const spec = statsQuerySpec(range);
  const base = getAdminDb()
    .collection(COLLECTIONS.attendance)
    .select("personId", "date", "late", "earlyLeave", "direction", "ts");
  const [snap, people, holidays] = await Promise.all([
    // One extra doc so exactly STATS_QUERY_LIMIT rows is not reported as truncated.
    applySpec(base, { ...spec, limit: spec.limit + 1 }).get(),
    loadPeopleWithIds(),
    loadHolidays(),
  ]);
  return {
    punches: snap.docs.slice(0, STATS_QUERY_LIMIT).map((d) => toAttendance(d.data())),
    people: people.map((p) => ({ id: p.id, active: p.active })),
    holidays,
    truncated: snap.size > STATS_QUERY_LIMIT,
  };
}
