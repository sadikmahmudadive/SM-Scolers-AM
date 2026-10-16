import { COLLECTIONS } from "@hrm/shared";
import { DashboardLive, type DashboardPerson, type InitialPunch } from "@/components/dashboard/dashboard-live";
import { loadPeopleWithIds, loadTimeZone, toAttendance } from "@/lib/attendance-loader";
import { getAdminDb } from "@/lib/firebase-admin";
import { todayInZone } from "@/lib/org-time";
import { requireRole } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  await requireRole("admin");
  const tz = await loadTimeZone();
  const today = todayInZone(tz, new Date());
  const db = getAdminDb();
  const [people, attendance, sms] = await Promise.all([
    loadPeopleWithIds(),
    db.collection(COLLECTIONS.attendance).where("date", "==", today).get(),
    db.collection(COLLECTIONS.smsLog).where("date", "==", today).get(),
  ]);
  const dashPeople: DashboardPerson[] = people.map((p) => ({ id: p.id, name: p.name, kind: p.kind, active: p.active }));
  const initialPunches: InitialPunch[] = attendance.docs.map((d) => {
    const a = toAttendance(d.data());
    return {
      id: d.id,
      personId: a.personId,
      ts: a.ts.getTime(),
      direction: a.direction,
      late: a.late,
      earlyLeave: a.earlyLeave,
    };
  });
  const initialSmsStatuses = sms.docs.map((d) => String(d.data().status ?? ""));
  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <DashboardLive
        key={today}
        tz={tz}
        people={dashPeople}
        today={today}
        initialPunches={initialPunches}
        initialSmsStatuses={initialSmsStatuses}
      />
    </main>
  );
}
