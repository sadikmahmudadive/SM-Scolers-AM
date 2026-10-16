import Link from "next/link";
import type { PersonRow } from "@/lib/people-list";

export function PeopleTable({ items }: { items: PersonRow[] }) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No people match.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-accent text-accent-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">ID</th>
            <th scope="col" className="px-3 py-2 font-medium">Name</th>
            <th scope="col" className="px-3 py-2 font-medium">Kind</th>
            <th scope="col" className="px-3 py-2 font-medium">Class</th>
            <th scope="col" className="px-3 py-2 font-medium">Phone</th>
            <th scope="col" className="px-3 py-2 font-medium">Device</th>
            <th scope="col" className="px-3 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id} className="border-t border-border">
              <td className="px-3 py-2 tabular-nums">{p.id}</td>
              <td className="px-3 py-2">
                <Link href={`/people/${encodeURIComponent(p.id)}`} className="font-medium underline-offset-4 hover:underline">
                  {p.name}
                </Link>
              </td>
              <td className="px-3 py-2 capitalize">{p.kind}</td>
              <td className="px-3 py-2">{[p.className, p.section].filter(Boolean).join(" ") || "-"}</td>
              <td className="px-3 py-2">{p.phone ?? "-"}</td>
              <td className="px-3 py-2">{p.deviceEnrolled ? "Enrolled" : "Not enrolled"}</td>
              <td className="px-3 py-2">{p.active ? "Active" : "Inactive"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
