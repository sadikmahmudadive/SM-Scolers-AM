import { DayRowsTable, StatusBadge } from "@/components/day-rows-table";
import { loadHolidays, loadTimeZone } from "@/lib/attendance-loader";
import { todayInZone } from "@/lib/org-time";
import { buildDayRows, lastNDays, todayStatus } from "@/lib/person-days";
import { adminScopedDeps, loadPersonDays, loadSelf } from "@/lib/scoped-loaders";
import { requireRole } from "@/lib/session";

export default async function MePage() {
  const session = await requireRole("staff");
  const deps = adminScopedDeps();
  const self = await loadSelf(session, deps);

  if (!self.linked) {
    return (
      <main className="space-y-4 p-6">
        <h1 className="text-2xl font-semibold">My attendance</h1>
        <p className="text-sm text-muted-foreground">
          Your account is not linked to a person yet - ask an administrator.
        </p>
      </main>
    );
  }

  const { person } = self;
  const [tz, holidays] = await Promise.all([loadTimeZone(), loadHolidays()]);
  const today = todayInZone(tz, new Date());
  const range = lastNDays(today, 30);
  // person.id comes from the verified session (loadSelf), never from the URL.
  const punches = await loadPersonDays(person.id, range, deps);

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">My attendance</h1>
      <section aria-labelledby="profile" className="space-y-1 text-sm">
        <h2 id="profile" className="text-lg font-semibold">{person.name}</h2>
        <p>ID {person.id}</p>
        <p>Class/section: {[person.className, person.section].filter(Boolean).join(" ") || "-"}</p>
        <p>Phone: {person.phone ?? "-"}</p>
        <p>
          Today: <StatusBadge status={todayStatus(punches, today, holidays.includes(today))} />
        </p>
      </section>
      <section aria-labelledby="recent" className="space-y-2">
        <h2 id="recent" className="text-lg font-semibold">Last 30 days</h2>
        <DayRowsTable rows={buildDayRows(punches, range, holidays, tz)} caption="Your attendance for the last 30 days" />
      </section>
    </main>
  );
}
