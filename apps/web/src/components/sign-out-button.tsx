"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export function SignOutButton() {
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try {
      await fetch("/api/session", { method: "DELETE" });
    } finally {
      window.location.assign("/login");
    }
  }
  return (
    <Button type="button" variant="outline" size="sm" className="w-full" onClick={signOut} disabled={busy}>
      {busy ? "Signing out..." : "Sign out"}
    </Button>
  );
}
