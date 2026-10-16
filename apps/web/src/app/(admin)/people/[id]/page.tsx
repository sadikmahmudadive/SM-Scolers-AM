import Link from "next/link";
import { notFound } from "next/navigation";
import { COLLECTIONS } from "@hrm/shared";
import { PersonForm } from "@/components/people/person-form";
import { PERSON_ID_PATTERN } from "@/lib/csv";
import { getAdminDb } from "@/lib/firebase-admin";
import type { PersonFormValues } from "@/lib/person-form-schema";
import { requireRole } from "@/lib/session";

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
    </main>
  );
}
