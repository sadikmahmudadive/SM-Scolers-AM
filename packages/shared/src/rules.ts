export type Schedule = {
  /** Arrival window start, "HH:mm". Arriving before it is on time. */
  start: string;
  /** Arrival window end, "HH:mm". */
  end: string;
  /** Minutes of grace after `end` before the first punch counts as late. */
  graceMin: number;
  /** Optional end-of-day time, "HH:mm". */
  dismissal?: string;
};

export type PunchEvalInput = {
  /** Local time of the punch, "HH:mm:ss". */
  time: string;
  schedule: Schedule | null;
  /** Minutes since the person's previous punch today, or null for the first punch. */
  previousPunchMinutesAgo: number | null;
  isHoliday: boolean;
};

export type PunchFlags = { late: boolean; earlyLeave: boolean; duplicate: boolean };

/** A punch within this many minutes of the previous one is a duplicate scan. */
export const DUPLICATE_WINDOW_MIN = 5;

/** Seconds since midnight for "HH:mm" or "HH:mm:ss". */
function toSeconds(hhmm: string): number {
  const [h = "0", m = "0", s = "0"] = hhmm.split(":");
  return Number(h) * 3600 + Number(m) * 60 + Number(s);
}

export function evaluatePunch(input: PunchEvalInput): PunchFlags {
  const { time, schedule, previousPunchMinutesAgo, isHoliday } = input;

  // Duplicate is computed first and independently of holiday/schedule:
  // a double scan is a duplicate even when no other flag could apply.
  const duplicate =
    previousPunchMinutesAgo !== null && previousPunchMinutesAgo < DUPLICATE_WINDOW_MIN;

  if (duplicate || isHoliday || schedule === null) {
    return { late: false, earlyLeave: false, duplicate };
  }

  const t = toSeconds(time);
  const isFirstPunch = previousPunchMinutesAgo === null;

  const late = isFirstPunch && t > toSeconds(schedule.end) + schedule.graceMin * 60;
  const earlyLeave =
    !isFirstPunch && schedule.dismissal !== undefined && t < toSeconds(schedule.dismissal);

  return { late, earlyLeave, duplicate };
}

/** Device status codes: 0/3/4 are check-in, 1/2/5 check-out, anything else defaults to "in". */
export function directionFromStatus(raw: string): "in" | "out" {
  switch (raw) {
    case "1":
    case "2":
    case "5":
      return "out";
    default:
      return "in";
  }
}
