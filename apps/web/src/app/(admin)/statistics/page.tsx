import Link from "next/link";
import { StatisticsChart } from "@/components/statistics/chart-loader";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { loadTimeZone } from "@/lib/attendance-loader";
import { todayInZone } from "@/lib/org-time";
import { requireRole } from "@/lib/session";
import { computeDailyStats, rangeFromPreset, summarizeStats, type Preset } from "@/lib/stats";
import { loadStatsData } from "@/lib/stats-loader";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function one(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

export default async function StatisticsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("admin");
  const sp = await searchParams;
  const tz = await loadTimeZone();
  const today = todayInZone(tz, new Date());
  const from = one(sp.from);
  const to = one(sp.to);
  const preset: Preset = from && to ? "custom" : one(sp.preset) === "7d" ? "7d" : "30d";

  let error: string | null = null;
  let range = rangeFromPreset("30d", today);
  let rows: ReturnType<typeof computeDailyStats> = [];
  let truncated = false;
  try {
    range = rangeFromPreset(preset, today, preset === "custom" ? { from, to } : undefined);
    const data = await loadStatsData(range);
    truncated = data.truncated;
    rows = computeDailyStats(data.punches, data.people, range, data.holidays);
  } catch (e) {
    error = e instanceof Error ? e.message : "Could not load statistics";
  }
  const summary = summarizeStats(rows);
  const labelClass = "mb-1 block text-xs text-muted-foreground";
  const cards = [
    { label: "Avg present / day", value: summary.avgPresent },
    { label: "Avg late / day", value: summary.avgLate },
    { label: "Total punches", value: summary.totalPunches },
    { label: "Days with data", value: summary.days },
  ];

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Statistics</h1>
      <div className="flex flex-wrap items-end gap-2">
        <Link href="/statistics?preset=7d" aria-current={preset === "7d" ? "true" : undefined} className={buttonVariants({ variant: preset === "7d" ? "default" : "outline" })}>
          Last 7 days
        </Link>
        <Link href="/statistics?preset=30d" aria-current={preset === "30d" ? "true" : undefined} className={buttonVariants({ variant: preset === "30d" ? "default" : "outline" })}>
          Last 30 days
        </Link>
        <form method="get" className="flex flex-wrap items-end gap-2" role="search">
          <div>
            <label htmlFor="from" className={labelClass}>From</label>
            <Input id="from" name="from" type="date" defaultValue={range.from} required />
          </div>
          <div>
            <label htmlFor="to" className={labelClass}>To</label>
            <Input id="to" name="to" type="date" defaultValue={range.to} required />
          </div>
          <button type="submit" className={buttonVariants({ variant: preset === "custom" ? "default" : "outline" })}>
            Custom range
          </button>
        </form>
      </div>

      {error ? (
        <p role="alert" className="rounded-md border border-destructive p-3 text-sm text-destructive">{error}</p>
      ) : (
        <>
          {truncated ? (
            <p role="status" className="rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
              This range has more than 50000 punches; only the most recent are included, so older days may be undercounted. Narrow the range.
            </p>
          ) : null}
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {cards.map((c) => (
              <div key={c.label} className="rounded-lg border border-border p-4">
                <dt className="text-xs text-muted-foreground">{c.label}</dt>
                <dd className="text-2xl font-semibold">{c.value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-sm text-muted-foreground">
            {range.from} to {range.to}. Days without any punches (weekends, closures) are shown as gaps and holidays are omitted.
          </p>
          <StatisticsChart rows={rows} range={range} />
        </>
      )}
    </main>
  );
}
