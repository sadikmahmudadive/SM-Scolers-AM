"use client";

import { useRef, useState, useTransition } from "react";
import { exportBackup, restoreBackup } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormMessage } from "./shared";

const MAX_BYTES = 5 * 1024 * 1024;

export function Backup() {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [confirming, setConfirming] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function download() {
    setError(null);
    setOk(null);
    start(async () => {
      try {
        const json = await exportBackup();
        const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `hrm-configuration-backup-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setOk("Configuration backup downloaded.");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not export");
      }
    });
  }

  function pick(f: File | undefined) {
    setError(null);
    setOk(null);
    setConfirming(false);
    if (f && f.size > MAX_BYTES) {
      setFile(null);
      setError("File too large (max 5 MB)");
      return;
    }
    setFile(f ?? null);
  }

  function restore() {
    if (!file) return;
    setError(null);
    setOk(null);
    start(async () => {
      try {
        const text = await file.text();
        const r = await restoreBackup(text);
        if (r.ok) {
          const parts = Object.entries(r.restored).map(([k, n]) => `${n} ${k}`);
          setOk(`Restored: ${parts.join(", ")}.`);
          setFile(null);
          if (fileRef.current) fileRef.current.value = "";
        } else setError(r.error);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not restore");
      }
      setConfirming(false);
    });
  }

  return (
    <div className="max-w-xl space-y-8">
      <section aria-labelledby="backup-export" className="space-y-2">
        <h2 id="backup-export" className="font-semibold">Download configuration backup</h2>
        <p className="text-sm text-muted-foreground">
          People, schedules, holidays, devices and settings as one JSON file.
        </p>
        <p className="text-sm font-medium">
          This is not a full backup: attendance history and SMS logs are NOT included. To back up everything, use a
          Firestore managed export or point-in-time recovery (see the deployment guide).
        </p>
        <Button type="button" disabled={pending} onClick={download}>
          Download configuration backup
        </Button>
      </section>

      <section aria-labelledby="backup-restore" className="space-y-2">
        <h2 id="backup-restore" className="font-semibold">Restore configuration backup</h2>
        <p className="text-sm text-muted-foreground">
          Every record is checked first; if anything is invalid nothing is written. Records in the file overwrite
          existing records with the same ID (including guardian links, manager assignments and device-enrolment
          flags). Records that are not in the file are kept; nothing is deleted.
        </p>
        <div className="space-y-1">
          <Label htmlFor="backup-file">Configuration backup file</Label>
          <Input
            id="backup-file"
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            disabled={pending}
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </div>
        {file && !confirming && (
          <Button type="button" variant="outline" disabled={pending} onClick={() => setConfirming(true)}>
            Restore {file.name}
          </Button>
        )}
        {file && confirming && (
          <div role="alertdialog" aria-label="Confirm restore" className="space-y-2 rounded-md border border-border p-3">
            <p className="text-sm">
              Restoring overwrites every existing document that has the same ID as a document in this file, including
              guardian links, manager assignments and device-enrolment flags. Nothing is deleted. This cannot be
              undone. Continue?
            </p>
            <div className="flex gap-2">
              <Button type="button" disabled={pending} onClick={restore}>
                {pending ? "Restoring..." : "Yes, overwrite and restore"}
              </Button>
              <Button type="button" variant="ghost" disabled={pending} onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </section>
      <FormMessage error={error} ok={ok} />
    </div>
  );
}
