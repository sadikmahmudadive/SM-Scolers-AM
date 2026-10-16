import Link from "next/link";
import { PersonForm } from "@/components/people/person-form";
import { requireRole } from "@/lib/session";

export default async function NewPersonPage() {
  await requireRole("admin");
  return (
    <main className="space-y-4 p-6">
      <Link href="/people" className="text-sm underline-offset-4 hover:underline">
        Back to people
      </Link>
      <h1 className="text-2xl font-semibold">Add person</h1>
      <PersonForm mode="create" />
    </main>
  );
}
