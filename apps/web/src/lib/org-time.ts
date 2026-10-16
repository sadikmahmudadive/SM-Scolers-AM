export const DEFAULT_TIME_ZONE = "Asia/Dhaka";

function validZone(tz: string): string {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return tz;
  } catch {
    return DEFAULT_TIME_ZONE;
  }
}

/** Org-local yyyy-MM-dd for the instant `now`. Invalid zones fall back to Asia/Dhaka. */
export function todayInZone(tz: string, now: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: validZone(tz),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

/** Org-local HH:mm (24h) for the instant `d`. */
export function formatTimeInZone(tz: string, d: Date): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: validZone(tz),
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  return `${get("hour")}:${get("minute")}`;
}
