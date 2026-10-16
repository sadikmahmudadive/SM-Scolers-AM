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

/**
 * True when the org-local date is LATER than the rendered date. A client clock behind the server
 * (rendered date in the future) never triggers a refresh, so it cannot cause endless refreshes.
 * yyyy-MM-dd compares correctly as a string.
 */
export function shouldRollOver(renderedToday: string, tz: string, now: Date): boolean {
  return todayInZone(tz, now) > renderedToday;
}
