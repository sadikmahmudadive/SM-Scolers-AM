import Link from "next/link";
import { COLLECTIONS } from "@hrm/shared";
import { PeopleTable } from "@/components/people/people-table";
import { CsvImport } from "@/components/people/csv-import";
import { SyncButton } from "@/components/people/sync-button";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getAdminDb } from "@/lib/firebase-admin";
import { listPeople, type PersonRow } from "@/lib/people-list";
import { requireRole } from "@/lib/session";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function one(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

// The school roster is small (hundreds), so filter/search/paginate in memory after one read.
async function loadPeople(): Promise<PersonRow[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.people).get();
  return snap.docs.map((d) => {
    const x = d.data();
    return {
      id: d.id,
      name: String(x.name ?? ""),
      kind: x.kind,
      className: x.className || undefined,
      section: x.section || undefined,
      phone: x.phone || undefined,
      active: x.active !== false,
      deviceEnrolled: x.deviceEnrolled === true,
    };
  });
}

export default async function PeoplePage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("admin");
  const sp = await searchParams;
  const q = one(sp.q);
  const kind = one(sp.kind);
  const className = one(sp.class);
  const all = await loadPeople();
  const classes = [...new Set(all.map((p) => p.className).filter((c): c is string => !!c))].sort();
  const result = listPeople(all, { q, kind, className, page: Number(one(sp.page)) || 1 });

  const href = (page: number) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (kind) p.set("kind", kind);
    if (className) p.set("class", className);
    if (page > 1) p.set("page", String(page));
    const s = p.toString();
    return s ? `/people?${s}` : "/people";
  };

  const selectClass =
    "h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <main className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">People</h1>
        <div className="flex flex-wrap items-start gap-2">
          <Link href="/people/new" className={buttonVariants()}>
            Add person
          </Link>
          <CsvImport />
          <SyncButton />
        </div>
      </div>

      <form method="get" className="flex flex-wrap items-end gap-2" role="search">
        <div>
          <label htmlFor="q" className="sr-only">
            Search
          </label>
          <Input id="q" name="q" defaultValue={q} placeholder="Search name or ID" className="w-56" />
        </div>
        <div>
          <label htmlFor="kind" className="sr-only">
            Kind
          </label>
          <select id="kind" name="kind" defaultValue={kind} className={selectClass}>
            <option value="">All kinds</option>
            <option value="student">Students</option>
            <option value="teacher">Teachers</option>
            <option value="staff">Staff</option>
          </select>
        </div>
        <div>
          <label htmlFor="class" className="sr-only">
            Class
          </label>
          <select id="class" name="class" defaultValue={className} className={selectClass}>
            <option value="">All classes</option>
            {classes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className={buttonVariants({ variant: "outline" })}>
          Filter
        </button>
      </form>

      <p className="text-sm text-muted-foreground" aria-live="polite">
        {result.total} total
      </p>
      <PeopleTable items={result.items} />

      <nav aria-label="Pagination" className="flex items-center gap-3 text-sm">
        {result.page > 1 ? (
          <Link href={href(result.page - 1)}>Previous</Link>
        ) : (
          <span className="text-muted-foreground">Previous</span>
        )}
        <span>
          Page {result.page} of {result.pages}
        </span>
        {result.page < result.pages ? (
          <Link href={href(result.page + 1)}>Next</Link>
        ) : (
          <span className="text-muted-foreground">Next</span>
        )}
      </nav>
    </main>
  );
}
