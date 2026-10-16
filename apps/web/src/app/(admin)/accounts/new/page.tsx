import Link from "next/link";
import { CreateAccountForm } from "@/components/accounts/create-account-form";
import { loadPeopleOptions } from "@/lib/accounts-loader";
import { requireRole } from "@/lib/session";

export default async function NewAccountPage() {
  await requireRole("admin");
  const people = await loadPeopleOptions();
  return (
    <main className="space-y-4 p-6">
      <Link href="/accounts" className="text-sm underline-offset-4 hover:underline">
        Back to accounts
      </Link>
      <h1 className="text-2xl font-semibold">Create account</h1>
      <CreateAccountForm people={people.options} truncated={people.truncated} />
    </main>
  );
}
