import Link from "next/link";
import { DayRowsTable, StatusBadge } from "@/components/day-rows-table";
import { loadHolidays, loadTimeZone } from "@/lib/attendance-loader";
import { todayInZone } from "@/lib/org-time";
import { buildDayRows, lastNDays, todayStatus } from "@/lib/person-days";
import { adminScopedDeps, loadChildren, loadSelectedDays, loadTodayPunches } from "@/lib/scoped-loaders";
import { CHILDREN_LIMIT, resolveSelection } from "@/lib/scoped-queries";
import { requireRole } from "@/lib/session";

export default async function ChildrenPage({ searchParams }: { searchParams: Promise<{ child?: string | string[] }> }) {
  const session = await requireRole("guardian");
  const sp = await searchParams;
  const requested = typeof sp.child === "string" ? sp.child : undefined;

  const deps = adminScopedDeps();
  const [tz, holidays, { children, truncated }] = await Promise.all([
    loadTimeZone(),
    loadHolidays(),
    loadChildren(session, deps),
  ]);
  const today = todayInZone(tz, new Date());
  const ids = children.map((c) => c.id);
  const range = lastNDays(today, 30);
  const [todayPunches, selected] = await Promise.all([
    loadTodayPunches(ids, today, deps),
    loadSelectedDays(resolveSelection(requested, ids) ?? undefined, ids, range, deps),
  ]);
  const selectedChild = children.find((c) => c.id === selected?.personId);

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Children</h1>
      {children.length === 0 ? (
        <p className="text-sm text-muted-foreground">No children are linked to your account yet - ask the school office.</p>
      ) : (
        <>
          {truncated && (
            <p role="status" className="text-sm text-muted-foreground">
              Showing the first {CHILDREN_LIMIT} children only.
            </p>
          )}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {children.map((c) => (
              <li key={c.id} className="rounded-md border border-border p-4">
                <Link
                  href={`/children?child=${encodeURIComponent(c.id)}`}
                  className={c.id === selected?.personId ? "font-semibold underline" : "underline-offset-4 hover:underline"}
                >
                  {c.name}
                </Link>
                <p className="text-sm text-muted-foreground">
                  {[c.className, c.section].filter(Boolean).join(" ") || "No class set"}
                </p>
                <p className="mt-2 text-sm">
                  Today: <StatusBadge status={todayStatus(todayPunches.get(c.id) ?? [], today, holidays.includes(today))} />
                </p>
              </li>
            ))}
          </ul>
          {selected && selectedChild && (
            <section aria-labelledby="recent" className="space-y-2">
              <h2 id="recent" className="text-lg font-semibold">
                {selectedChild.name} - last 30 days
              </h2>
              <DayRowsTable
                rows={buildDayRows(selected.punches, range, holidays, tz)}
                caption={`Attendance for ${selectedChild.name}`}
              />
            </section>
          )}
        </>
      )}
    </main>
  );
}
