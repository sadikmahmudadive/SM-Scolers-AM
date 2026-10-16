import Link from "next/link";
import { AccountsTable } from "@/components/accounts/accounts-table";
import { buttonVariants } from "@/components/ui/button";
import { loadAccountRows, loadPeopleOptions, MAX_ACCOUNTS } from "@/lib/accounts-loader";
import { requireRole } from "@/lib/session";

export default async function AccountsPage() {
  const session = await requireRole("admin");
  const [{ rows, truncated }, people] = await Promise.all([loadAccountRows(), loadPeopleOptions()]);
  return (
    <main className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Accounts</h1>
        <Link href="/accounts/new" className={buttonVariants()}>
          Create account
        </Link>
      </div>
      {truncated && (
        <p role="status" className="text-sm text-muted-foreground">
          Showing the first {MAX_ACCOUNTS} accounts; more exist and are not listed.
        </p>
      )}
      <AccountsTable rows={rows} currentUid={session.uid} people={people.options} truncated={people.truncated} />
    </main>
  );
}
