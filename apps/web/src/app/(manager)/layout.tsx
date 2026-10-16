import { requireRole } from "@/lib/session";

// Pages/data loaders must still call requireRole/getSession - shared layouts are not re-rendered on soft navigation.
export default async function Layout({ children }: { children: React.ReactNode }) {
  await requireRole("manager", "admin");
  return <>{children}</>;
}
