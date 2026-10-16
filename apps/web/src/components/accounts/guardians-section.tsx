"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { linkGuardian, unlinkGuardian } from "@/actions/accounts";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/components/settings/shared";

export type LinkedGuardian = { uid: string; email: string; displayName: string; known: boolean };
export type AccountOption = { uid: string; email: string; displayName: string };

function labelOf(a: AccountOption): string {
  return a.displayName ? `${a.displayName} (${a.email})` : a.email;
}

export function GuardiansSection({
  personId,
  linked,
  available,
}: {
  personId: string;
  linked: LinkedGuardian[];
  /** Guardian-role accounts not yet linked. */
  available: AccountOption[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<{ ok: true } | { ok: false; error: string }>) {
    setError(null);
    setBusy(true);
    try {
      const r = await fn();
      if (!r.ok) return setError(r.error);
      setSelected("");
      setConfirming(null);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="guardians" className="max-w-xl space-y-3">
      <h2 id="guardians" className="text-lg font-semibold">Guardians</h2>
      {linked.length === 0 ? (
        <p className="text-sm text-muted-foreground">No guardian accounts linked.</p>
      ) : (
        <ul className="space-y-2">
          {linked.map((g) => (
            <li key={g.uid} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>{g.known ? labelOf(g) : "unknown account"}</span>
              {confirming === g.uid ? (
                <span role="alertdialog" aria-label="Confirm unlink" className="flex items-center gap-2">
                  <span>Unlink?</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-destructive text-destructive"
                    disabled={busy}
                    onClick={() => run(() => unlinkGuardian(personId, g.uid))}
                  >
                    Yes, unlink
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setConfirming(null)}>
                    Cancel
                  </Button>
                </span>
              ) : (
                <Button type="button" size="sm" variant="outline" onClick={() => setConfirming(g.uid)}>
                  Unlink<span className="sr-only"> {g.known ? labelOf(g) : "unknown account"}</span>
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="add-guardian">Add guardian</Label>
          <select
            id="add-guardian"
            className={selectClass}
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">Select a guardian account</option>
            {available.map((a) => (
              <option key={a.uid} value={a.uid}>
                {labelOf(a)}
              </option>
            ))}
          </select>
        </div>
        <Button type="button" disabled={!selected || busy} onClick={() => run(() => linkGuardian(personId, selected))}>
          Link guardian
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
