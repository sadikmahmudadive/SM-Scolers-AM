import Link from "next/link";
import { notFound } from "next/navigation";
import { COLLECTIONS } from "@hrm/shared";
import { buttonVariants } from "@/components/ui/button";
import { loadPersonPunches, loadTimeZone } from "@/lib/attendance-loader";
import { formatTimeInZone, todayInZone } from "@/lib/org-time";
import { rangeFromPreset } from "@/lib/stats";
import { PersonForm } from "@/components/people/person-form";
import { PERSON_ID_PATTERN } from "@/lib/csv";
import { getAdminDb } from "@/lib/firebase-admin";
import type { PersonFormValues } from "@/lib/person-form-schema";
import { requireRole } from "@/lib/session";
import { GuardiansSection } from "@/components/accounts/guardians-section";
import { ManagerSelect } from "@/components/accounts/manager-select";
import { loadAccountsWithRoles, resolveAccounts } from "@/lib/accounts-loader";

export default async function PersonPage({ params }: { params: Promise<{ id: string }> }) {
  await requireRole("admin");
  const { id: rawId } = await params;
  const id = decodeURIComponent(rawId);
  if (!PERSON_ID_PATTERN.test(id)) notFound();
  const snap = await getAdminDb().collection(COLLECTIONS.people).doc(id).get();
  if (!snap.exists) notFound();
  const x = snap.data() ?? {};
  const initial: PersonFormValues = {
    id,
    name: String(x.name ?? ""),
    kind: x.kind,
    phone: x.phone ?? "",
    fatherPhone: x.fatherPhone ?? "",
    motherPhone: x.motherPhone ?? "",
    className: x.className ?? "",
    section: x.section ?? "",
    departmentId: x.departmentId ?? "",
    managerId: x.managerId ?? "",
    active: x.active !== false,
  };
  const guardianUids: string[] = Array.isArray(x.guardianUids)
    ? x.guardianUids.filter((u: unknown): u is string => typeof u === "string")
    : [];
  const isStudent = x.kind === "student";
  const [linked, guardianAccounts, managers] = await Promise.all([
    isStudent ? resolveAccounts(guardianUids) : Promise.resolve([]),
    isStudent ? loadAccountsWithRoles("guardian") : Promise.resolve([]),
    loadAccountsWithRoles("manager", "admin"),
  ]);
  const available = guardianAccounts.filter((a) => !guardianUids.includes(a.uid));
  const tz = await loadTimeZone();
  const range = rangeFromPreset("30d", todayInZone(tz, new Date()));
  const history = await loadPersonPunches(id, range);
  const pdfHref = `/api/reports/person/${encodeURIComponent(id)}?from=${range.from}&to=${range.to}`;
  return (
    <main className="space-y-4 p-6">
      <Link href="/people" className="text-sm underline-offset-4 hover:underline">
        Back to people
      </Link>
      <h1 className="text-2xl font-semibold">{initial.name}</h1>
      <p className="text-sm text-muted-foreground">
        ID {id} - {x.deviceEnrolled ? "enrolled on device" : "not enrolled on device"}
      </p>
      <PersonForm mode="edit" initial={initial} />
      <ManagerSelect personId={id} current={typeof x.managerId === "string" ? x.managerId : ""} managers={managers} />
      {isStudent && <GuardiansSection personId={id} linked={linked} available={available} />}
      <section aria-labelledby="history" className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="history" className="text-lg font-semibold">Recent attendance (last 30 days)</h2>
          <a href={pdfHref} className={buttonVariants({ variant: "outline" })}>
            Download PDF (last 30 days)
          </a>
        </div>
        {history.length === 0 ? (
          <p className="text-sm text-muted-foreground">No punches in this period.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th scope="col" className="py-1">Date</th>
                <th scope="col">Time</th>
                <th scope="col">Direction</th>
                <th scope="col">Flags</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={`${h.date}-${h.ts.getTime()}-${i}`} className="border-b border-border">
                  <td className="py-1">{h.date}</td>
                  <td>{formatTimeInZone(tz, h.ts)}</td>
                  <td>{h.direction}</td>
                  <td>{[h.late ? "Late" : "", h.earlyLeave ? "Early leave" : ""].filter(Boolean).join(", ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
