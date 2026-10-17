"use client";

import { Button } from "@/components/ui/button";

/** Shared body of the per-role-group error boundaries (app/(role)/error.tsx). */
export function RouteError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="max-w-xl space-y-3 rounded-md border border-border p-4">
      <h2 className="font-semibold">This page could not be loaded</h2>
      <p className="text-sm text-muted-foreground">
        Something went wrong while loading the data, possibly a temporary network or database problem. Try again;
        if it keeps happening, reload the page or contact the administrator.
      </p>
      <Button type="button" onClick={() => reset()}>
        Try again
      </Button>
    </div>
  );
}
