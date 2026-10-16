import Link from "next/link";
import { SignOutButton } from "@/components/sign-out-button";
import { requireRole } from "@/lib/session";

// Only pages that exist are linked; add Settings as it is built.
const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/people", label: "People" },
  { href: "/attendance", label: "Attendance" },
  { href: "/today", label: "Present today" },
  { href: "/statistics", label: "Statistics" },
];

// Pages/data loaders must still call requireRole/getSession - shared layouts are not re-rendered on soft navigation.
export default async function Layout({ children }: { children: React.ReactNode }) {
  await requireRole("admin");
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="flex shrink-0 flex-col gap-4 border-b border-border p-4 md:w-56 md:border-b-0 md:border-r">
        <span className="text-lg font-semibold">HRM</span>
        <nav aria-label="Main" className="flex flex-row gap-1 md:flex-col">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="md:mt-auto">
          <SignOutButton />
        </div>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
