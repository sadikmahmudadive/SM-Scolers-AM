import type { Attendance } from "@hrm/shared";

export type DailyStat = {
  date: string;
  present: number;
  absent: number;
  late: number;
  punches: number;
  noData: boolean;
};

export type DateRange = { from: string; to: string };
export const MAX_RANGE_DAYS = 366;
export class StatsInputError extends Error {}
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const DAY_MS = 86_400_000;

function parseDate(s: string): number {
  if (!DATE_RE.test(s)) throw new StatsInputError("Dates must be yyyy-MM-dd");
  const t = Date.parse(`${s}T00:00:00Z`);
  if (Number.isNaN(t) || new Date(t).toISOString().slice(0, 10) !== s) throw new StatsInputError("Invalid date");
  return t;
}

function fmt(t: number): string {
  return new Date(t).toISOString().slice(0, 10);
}

/** Inclusive list of yyyy-MM-dd dates; throws when from > to or the span exceeds `max` days. */
export function eachDate(range: DateRange, max = Infinity): string[] {
  const a = parseDate(range.from);
  const b = parseDate(range.to);
  if (a > b) throw new StatsInputError("From date must not be after To date");
  const span = Math.round((b - a) / DAY_MS) + 1;
  if (span > max) throw new StatsInputError(`Range must not exceed ${max} days`);
  const out: string[] = [];
  for (let t = a; t <= b; t += DAY_MS) out.push(fmt(t));
  return out;
}

export function computeDailyStats(
  punches: readonly Attendance[],
  people: readonly { id: string; active: boolean }[],
  range: DateRange,
  holidays: readonly string[],
): DailyStat[] {
  const dates = eachDate(range);
  const holiday = new Set(holidays);
  const activeIds = new Set(people.filter((p) => p.active).map((p) => p.id));
  const byDate = new Map<string, { total: number; present: Set<string>; late: Set<string> }>();
  for (const p of punches) {
    let d = byDate.get(p.date);
    if (!d) byDate.set(p.date, (d = { total: 0, present: new Set(), late: new Set() }));
    d.total += 1;
    if (!activeIds.has(p.personId)) continue;
    d.present.add(p.personId);
    if (p.late) d.late.add(p.personId);
  }
  return dates
    .filter((date) => !holiday.has(date))
    .map((date) => {
      const d = byDate.get(date);
      if (!d || d.total === 0) return { date, present: 0, absent: 0, late: 0, punches: 0, noData: true };
      return {
        date,
        present: d.present.size,
        absent: activeIds.size - d.present.size,
        late: d.late.size,
        punches: d.total,
        noData: false,
      };
    });
}

export type Preset = "7d" | "30d" | "custom";

export function rangeFromPreset(preset: Preset, today: string, custom?: DateRange): DateRange {
  const t = parseDate(today);
  if (preset === "7d") return { from: fmt(t - 6 * DAY_MS), to: today };
  if (preset === "30d") return { from: fmt(t - 29 * DAY_MS), to: today };
  if (!custom) throw new StatsInputError("Custom range requires from and to");
  eachDate(custom, MAX_RANGE_DAYS);
  return { from: custom.from, to: custom.to };
}

const round1 = (n: number) => Math.round(n * 10) / 10;

export function summarizeStats(rows: readonly DailyStat[]): {
  avgPresent: number;
  avgLate: number;
  totalPunches: number;
  days: number;
} {
  const data = rows.filter((r) => !r.noData);
  const totalPunches = rows.reduce((s, r) => s + r.punches, 0);
  if (data.length === 0) return { avgPresent: 0, avgLate: 0, totalPunches, days: 0 };
  return {
    avgPresent: round1(data.reduce((s, r) => s + r.present, 0) / data.length),
    avgLate: round1(data.reduce((s, r) => s + r.late, 0) / data.length),
    totalPunches,
    days: data.length,
  };
}
