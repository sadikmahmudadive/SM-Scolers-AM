import type { Attendance } from "@hrm/shared";
import { z } from "zod";
import type { Session } from "./access";
import { toCsv } from "./csv-export";
import { computeDailyStats, MAX_RANGE_DAYS, rangeFromPreset } from "./stats";

export type StatsData = {
  punches: Attendance[];
  people: { id: string; active: boolean }[];
  holidays: string[];
  truncated: boolean;
};

export type StatsExportDeps = {
  load: (range: { from: string; to: string }) => Promise<StatsData>;
};

const dateStr = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const statsRangeSchema = z.object({ from: dateStr, to: dateStr });

export const STATS_CSV_HEADER = ["date", "present", "absent", "late", "punches", "noData"] as const;

export async function exportStatsCsvWith(
  deps: StatsExportDeps,
  caller: Session | null,
  rawRange: { from: string; to: string },
): Promise<{ csv: string; truncated: boolean }> {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
  const parsed = statsRangeSchema.parse(rawRange);
  // custom preset validates ordering, real dates and the max span; "today" is unused for custom.
  const range = rangeFromPreset("custom", parsed.to, parsed);
  const data = await deps.load(range);
  const rows = computeDailyStats(data.punches, data.people, range, data.holidays);
  return {
    csv: toCsv(
      STATS_CSV_HEADER,
      rows.map((r) => [r.date, r.present, r.absent, r.late, r.punches, r.noData]),
    ),
    truncated: data.truncated,
  };
}

export { MAX_RANGE_DAYS };
