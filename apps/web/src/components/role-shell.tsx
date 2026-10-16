import { SignOutButton } from "@/components/sign-out-button";

export function RoleShell({
  roleLabel,
  userLabel,
  children,
}: {
  roleLabel: string;
  userLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-3">
        <div className="flex items-baseline gap-3">
          <span className="text-lg font-semibold">HRM</span>
          <span className="text-sm text-muted-foreground">{roleLabel}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{userLabel || "Signed in"}</span>
          <SignOutButton />
        </div>
      </header>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
