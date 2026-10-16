"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { assignManager } from "@/actions/accounts";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/components/settings/shared";
import type { AccountOption } from "./guardians-section";

export function ManagerSelect({
  personId,
  current,
  managers,
}: {
  personId: string;
  /** Current people.managerId (a manager account uid), or "". */
  current: string;
  managers: AccountOption[];
}) {
  const router = useRouter();
  const [value, setValue] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const unknownCurrent = current !== "" && !managers.some((m) => m.uid === current);

  async function save() {
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const r = await assignManager(personId, value === "" ? null : value);
      if (!r.ok) return setError(r.error);
      setSaved(true);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="manager" className="max-w-xl space-y-3">
      <h2 id="manager" className="text-lg font-semibold">Manager</h2>
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="manager-select">Manager account</Label>
          <select
            id="manager-select"
            className={selectClass}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setSaved(false);
            }}
          >
            <option value="">No manager</option>
            {unknownCurrent && <option value={current}>unknown account</option>}
            {managers.map((m) => (
              <option key={m.uid} value={m.uid}>
                {m.displayName ? `${m.displayName} (${m.email})` : m.email}
              </option>
            ))}
          </select>
        </div>
        <Button type="button" disabled={busy || value === current} onClick={save}>
          Save manager
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm text-muted-foreground">
          Saved.
        </p>
      )}
    </section>
  );
}
