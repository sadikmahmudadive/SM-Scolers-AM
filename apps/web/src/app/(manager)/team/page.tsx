import Link from "next/link";
import { StatusBadge, DayRowsTable } from "@/components/day-rows-table";
import { loadHolidays, loadTimeZone } from "@/lib/attendance-loader";
import { todayInZone } from "@/lib/org-time";
import { buildDayRows, lastNDays, todayStatus } from "@/lib/person-days";
import { adminScopedDeps, loadSelectedDays, loadTeam, loadTodayPunches } from "@/lib/scoped-loaders";
import { resolveSelection, TEAM_LIMIT } from "@/lib/scoped-queries";
import { requireRole } from "@/lib/session";

export default async function TeamPage({ searchParams }: { searchParams: Promise<{ person?: string | string[] }> }) {
  const session = await requireRole("manager", "admin");
  const sp = await searchParams;
  const requested = typeof sp.person === "string" ? sp.person : undefined;

  const deps = adminScopedDeps();
  const [tz, holidays, team] = await Promise.all([loadTimeZone(), loadHolidays(), loadTeam(session, deps)]);
  const today = todayInZone(tz, new Date());
  const ids = team.reports.map((p) => p.id);
  const selectedId = resolveSelection(requested, ids);
  const fourteen = lastNDays(today, 14);
  const [todayPunches, selected] = await Promise.all([
    loadTodayPunches(ids, today, deps),
    loadSelectedDays(selectedId ?? undefined, ids, fourteen, deps),
  ]);
  const selectedPerson = team.reports.find((p) => p.id === selected?.personId);

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Team</h1>
      {team.reports.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No team members assigned to you yet.
          {session.role === "admin" ? " Assign managers on the person page." : ""}
        </p>
      ) : (
        <>
          {team.truncated && (
            <p role="status" className="text-sm text-muted-foreground">
              Showing the first {TEAM_LIMIT} team members only.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Your team and today&apos;s status</caption>
              <thead>
                <tr className="border-b border-border text-left">
                  <th scope="col" className="py-1">Name</th>
                  <th scope="col">ID</th>
                  <th scope="col">Class</th>
                  <th scope="col">Today</th>
                </tr>
              </thead>
              <tbody>
                {team.reports.map((p) => (
                  <tr key={p.id} className="border-b border-border">
                    <td className="py-1">
                      <Link
                        href={`/team?person=${encodeURIComponent(p.id)}`}
                        className={p.id === selected?.personId ? "font-semibold underline" : "underline-offset-4 hover:underline"}
                      >
                        {p.name}
                      </Link>
                    </td>
                    <td>{p.id}</td>
                    <td>{[p.className, p.section].filter(Boolean).join(" ") || "-"}</td>
                    <td>
                      <StatusBadge status={todayStatus(todayPunches.get(p.id) ?? [], today, holidays.includes(today))} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selected && selectedPerson && (
            <section aria-labelledby="recent" className="space-y-2">
              <h2 id="recent" className="text-lg font-semibold">
                {selectedPerson.name} - last 14 days
              </h2>
              <DayRowsTable
                rows={buildDayRows(selected.punches, fourteen, holidays, tz)}
                caption={`Attendance for ${selectedPerson.name}`}
              />
            </section>
          )}
        </>
      )}
    </main>
  );
}
