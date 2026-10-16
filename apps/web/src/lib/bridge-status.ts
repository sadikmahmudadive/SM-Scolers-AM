export const BRIDGE_OFFLINE_AFTER_SEC = 90;

export type BridgeHealth = { state: "online" | "device-offline" | "bridge-offline"; since?: Date };

export function bridgeHealth(
  status: { heartbeat: Date; deviceOnline: boolean } | null,
  now: Date,
): BridgeHealth {
  if (!status) return { state: "bridge-offline" };
  const ageSec = (now.getTime() - status.heartbeat.getTime()) / 1000;
  if (ageSec > BRIDGE_OFFLINE_AFTER_SEC) return { state: "bridge-offline", since: status.heartbeat };
  return { state: status.deviceOnline ? "online" : "device-offline" };
}

export function formatSince(since: Date, now: Date): string {
  const sec = Math.max(0, Math.floor((now.getTime() - since.getTime()) / 1000));
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.floor(h / 24)} d ago`;
}
