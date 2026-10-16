"use client";

import { useState, useTransition } from "react";
import { importPeopleCsv } from "@/actions/people";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Outcome = { imported: number; errors: { row: number; message: string }[] };
const MAX_BYTES = 1024 * 1024;

export function CsvImport() {
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  async function onFile(file: File | undefined) {
    setOutcome(null);
    setFileError(null);
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setFileError("File too large (max 1 MB)");
      return;
    }
    const text = await file.text();
    start(async () => {
      try {
        setOutcome(await importPeopleCsv(text));
      } catch (e) {
        setFileError(e instanceof Error ? e.message : "Import failed");
      }
    });
  }

  return (
    <div>
      <Button type="button" variant="outline" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Import CSV
      </Button>
      {open && (
        <section aria-label="CSV import" className="mt-3 max-w-xl space-y-3 rounded-md border border-border p-4">
          <div className="space-y-1">
            <Label htmlFor="csv-file">CSV file</Label>
            <Input
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              disabled={pending}
              onChange={(e) => onFile(e.target.files?.[0])}
            />
            <p className="text-xs text-muted-foreground">
              Columns: id, name, kind, phone, fatherPhone, motherPhone, className, section. Existing IDs are skipped.
            </p>
          </div>
          {pending && (
            <p role="status" className="text-sm">
              Importing...
            </p>
          )}
          {fileError && (
            <p role="alert" className="text-sm text-destructive">
              {fileError}
            </p>
          )}
          {outcome && (
            <div role="status" className="space-y-2 text-sm">
              <p>
                Imported <strong>{outcome.imported}</strong> {outcome.imported === 1 ? "person" : "people"}
                {outcome.errors.length > 0 &&
                  `; ${outcome.errors.length} row${outcome.errors.length === 1 ? "" : "s"} skipped`}
                .
              </p>
              {outcome.errors.length > 0 && (
                <ul className="max-h-60 list-disc space-y-1 overflow-auto pl-5 text-destructive">
                  {outcome.errors.map((e, i) => (
                    <li key={i}>
                      Line {e.row}: {e.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
