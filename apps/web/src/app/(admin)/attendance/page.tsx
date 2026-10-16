import Link from "next/link";
import { ExportCsvButton } from "@/components/attendance/export-csv-button";
import { LogsTable } from "@/components/attendance/logs-table";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { loadLogs, loadTimeZone } from "@/lib/attendance-loader";
import { filterAndPage, type LogFilters } from "@/lib/attendance-queries";
import { PERSON_KINDS, type PersonKind } from "@/lib/csv";
import { todayInZone } from "@/lib/org-time";
import { requireRole } from "@/lib/session";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function one(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

export default async function AttendancePage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("admin");
  const sp = await searchParams;
  const tz = await loadTimeZone();
  const today = todayInZone(tz, new Date());
  const kindRaw = one(sp.kind);
  const filters: LogFilters = {
    from: one(sp.from) || today,
    to: one(sp.to) || today,
    personId: one(sp.person).trim() || undefined,
    kind: (PERSON_KINDS as readonly string[]).includes(kindRaw) ? (kindRaw as PersonKind) : undefined,
    className: one(sp.class).trim() || undefined,
  };
  const page = Number(one(sp.page)) || 1;

  let result: ReturnType<typeof filterAndPage> | null = null;
  let people = new Map();
  let error: string | null = null;
  try {
    const loaded = await loadLogs(filters);
    people = loaded.people;
    result = filterAndPage(loaded.punches, loaded.people, filters, page, undefined, loaded.truncated);
  } catch (e) {
    error = e instanceof Error ? e.message : "Could not load attendance";
  }

  const href = (n: number) => {
    const p = new URLSearchParams();
    p.set("from", filters.from);
    p.set("to", filters.to);
    if (filters.personId) p.set("person", filters.personId);
    if (filters.kind) p.set("kind", filters.kind);
    if (filters.className) p.set("class", filters.className);
    if (n > 1) p.set("page", String(n));
    return `/attendance?${p.toString()}`;
  };
  const current = result?.page ?? 1;
  const selectClass =
    "h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const labelClass = "mb-1 block text-xs text-muted-foreground";

  return (
    <main className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Attendance logs</h1>
        {!error ? <ExportCsvButton filters={filters} /> : null}
      </div>

      <form method="get" className="flex flex-wrap items-end gap-2" role="search">
        <div>
          <label htmlFor="from" className={labelClass}>From</label>
          <Input id="from" name="from" type="date" defaultValue={filters.from} required />
        </div>
        <div>
          <label htmlFor="to" className={labelClass}>To</label>
          <Input id="to" name="to" type="date" defaultValue={filters.to} required />
        </div>
        <div>
          <label htmlFor="person" className={labelClass}>Person ID</label>
          <Input id="person" name="person" defaultValue={filters.personId ?? ""} className="w-32" />
        </div>
        <div>
          <label htmlFor="kind" className={labelClass}>Kind</label>
          <select id="kind" name="kind" defaultValue={filters.kind ?? ""} className={selectClass}>
            <option value="">All kinds</option>
            <option value="student">Students</option>
            <option value="teacher">Teachers</option>
            <option value="staff">Staff</option>
          </select>
        </div>
        <div>
          <label htmlFor="class" className={labelClass}>Class</label>
          <Input id="class" name="class" defaultValue={filters.className ?? ""} className="w-28" />
        </div>
        <button type="submit" className={buttonVariants({ variant: "outline" })}>
          Filter
        </button>
      </form>

      {error ? (
        <p role="alert" className="rounded-md border border-destructive p-3 text-sm text-destructive">
          {error}
        </p>
      ) : result ? (
        <>
          {result.truncated ? (
            <p role="status" className="rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
              Showing the most recent 5000 records in this range; older ones are not listed. Narrow the date range or add a person filter to see everything.
            </p>
          ) : null}
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {result.total} record{result.total === 1 ? "" : "s"}
          </p>
          <LogsTable rows={result.rows} people={people} timeZone={tz} />
          <nav aria-label="Pagination" className="flex items-center gap-3 text-sm">
            {current > 1 ? <Link href={href(current - 1)}>Previous</Link> : <span className="text-muted-foreground">Previous</span>}
            <span>
              Page {current} of {result.pageCount}
            </span>
            {current < result.pageCount ? (
              <Link href={href(current + 1)}>Next</Link>
            ) : (
              <span className="text-muted-foreground">Next</span>
            )}
          </nav>
        </>
      ) : null}
    </main>
  );
}
