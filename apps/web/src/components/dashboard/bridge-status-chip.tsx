import { bridgeHealth, formatSince } from "@/lib/bridge-status";

export type BridgeInfo = {
  heartbeat: Date;
  deviceOnline: boolean;
  carrier?: string;
  gsmSignal?: number;
};

function Bars({ level }: { level: number }) {
  // gsmSignal is 0-31 (CSQ, 99 = unknown); map to 0-4 bars.
  const bars = level <= 0 || level === 99 ? 0 : Math.min(4, Math.ceil((level / 31) * 4));
  return (
    <span aria-label={`Signal ${bars} of 4`} role="img" className="inline-flex items-end gap-0.5">
      {[1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`w-1 rounded-sm ${i <= bars ? "bg-foreground" : "bg-border"}`}
          style={{ height: 4 + i * 3 }}
        />
      ))}
    </span>
  );
}

export function BridgeStatusChip({ status, now }: { status: BridgeInfo | null; now: Date }) {
  const h = bridgeHealth(status, now);
  const since = h.since ?? null;
  const text =
    h.state === "online"
      ? "Bridge online"
      : h.state === "device-offline"
        ? "Device offline"
        : since
          ? `Bridge offline since ${formatSince(since, now)}`
          : "Bridge offline";
  const dot = h.state === "online" ? "bg-green-500" : h.state === "device-offline" ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1">
      <p
        role="status"
        title={since ? `Last heartbeat ${since.toISOString()}` : undefined}
        className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-sm"
      >
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        {text}
      </p>
      {h.state === "online" && status && (status.carrier || status.gsmSignal !== undefined) ? (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          {status.carrier ? <span>{status.carrier}</span> : null}
          {status.gsmSignal !== undefined ? <Bars level={status.gsmSignal} /> : null}
        </p>
      ) : null}
    </div>
  );
}
