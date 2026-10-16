"use client";

import { useState, useTransition } from "react";
import { syncDeviceUsers } from "@/actions/people";
import { Button } from "@/components/ui/button";

export function SyncButton() {
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        disabled={pending}
        onClick={() =>
          start(async () => {
            try {
              await syncDeviceUsers();
              setMsg("Sync requested. The bridge will pick it up shortly.");
            } catch (e) {
              setMsg(e instanceof Error ? e.message : "Could not request sync");
            }
          })
        }
      >
        {pending ? "Requesting..." : "Sync from device"}
      </Button>
      <span role="status" className="text-xs text-muted-foreground">
        {msg}
      </span>
    </span>
  );
}
