"use client";

import { useId, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/components/settings/shared";

export type PersonOption = { id: string; name: string; kind: string };

type Props = {
  label: string;
  options: PersonOption[];
  value: string;
  onChange: (id: string) => void;
  truncated?: boolean;
  error?: string;
  disabled?: boolean;
};

/** Text filter + select. The select always keeps the current value so a filter never drops the selection. */
export function PersonPicker({ label, options, value, onChange, truncated, error, disabled }: Props) {
  const uid = useId();
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const filtered = needle
    ? options.filter((o) => o.name.toLowerCase().includes(needle) || o.id.toLowerCase().includes(needle))
    : options;
  const shown = value && !filtered.some((o) => o.id === value) ? [...options.filter((o) => o.id === value), ...filtered] : filtered;
  const errId = `${uid}-err`;
  return (
    <div className="space-y-1">
      <Label htmlFor={`${uid}-sel`}>{label}</Label>
      <Input
        aria-label={`Filter ${label.toLowerCase()} by name or ID`}
        placeholder="Filter by name or ID"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        disabled={disabled}
      />
      <select
        id={`${uid}-sel`}
        className={selectClass}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errId : undefined}
      >
        <option value="">None</option>
        {shown.map((o) => (
          <option key={o.id} value={o.id}>
            {o.name} ({o.id})
          </option>
        ))}
      </select>
      {truncated && (
        <p className="text-xs text-muted-foreground">Showing the first {options.length} people; use the filter to narrow.</p>
      )}
      {error && (
        <p id={errId} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
