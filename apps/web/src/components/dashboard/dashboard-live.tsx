"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { collection, doc, onSnapshot, query, where, type DocumentData } from "firebase/firestore";
import { computeKpis, latestPunches } from "@/lib/dashboard-metrics";
import { acquireLiveAuth, getClientDb, releaseLiveAuth } from "@/lib/firebase-live";
import { shouldRollOver } from "@/lib/org-time";
import { BridgeStatusChip, type BridgeInfo } from "./bridge-status-chip";
import { KpiCards } from "./kpi-cards";
import { LiveFeed, type FeedPunch } from "./live-feed";
import { PresenceGlobe } from "./presence-globe";

export type DashboardPerson = { id: string; name: string; kind: string; active: boolean };
/** Serializable punch (ts as epoch ms) for server-to-client props. */
export type InitialPunch = Omit<FeedPunch, "ts"> & { ts: number };

type LiveState = "connecting" | "live" | "failed";
type Bridge = { loaded: boolean; info: BridgeInfo | null };

const FEED_SIZE = 20;

function toDate(v: unknown): Date {
  if (v instanceof Date) return v;
  if (v && typeof (v as { toDate?: unknown }).toDate === "function") return (v as { toDate: () => Date }).toDate();
  return new Date(0);
}

function toPunch(id: string, x: DocumentData): FeedPunch {
  return {
    id,
    personId: String(x.personId ?? ""),
    ts: toDate(x.ts),
    direction: x.direction === "out" ? "out" : "in",
    late: x.late === true,
    earlyLeave: x.earlyLeave === true,
  };
}

export function DashboardLive({
  people,
  today,
  tz,
  initialPunches,
  initialSmsStatuses,
}: {
  people: DashboardPerson[];
  today: string;
  tz: string;
  initialPunches: InitialPunch[];
  initialSmsStatuses: string[];
}) {
  const [punches, setPunches] = useState<FeedPunch[]>(() =>
    initialPunches.map((p) => ({ ...p, ts: new Date(p.ts) })),
  );
  const [sms, setSms] = useState<{ status: string }[]>(() => initialSmsStatuses.map((status) => ({ status })));
  const [bridge, setBridge] = useState<Bridge>({ loaded: false, info: null });
  const [state, setState] = useState<LiveState>("connecting");
  const [now, setNow] = useState(() => new Date());
  const router = useRouter();

  // Re-evaluate bridge health every 15 s.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(id);
  }, []);

  // After org-local midnight, ask the server to re-render for the new date (remounts via key={today}).
  useEffect(() => {
    const id = setInterval(() => {
      if (shouldRollOver(today, tz, new Date())) router.refresh();
    }, 60_000);
    return () => clearInterval(id);
  }, [today, tz, router]);

  useEffect(() => {
    const unsubs: Array<() => void> = [];
    let cancelled = false;
    let acquired = false;
    const fail = () => setState("failed");
    acquireLiveAuth()
      .then(() => {
        acquired = true;
        if (cancelled) {
          releaseLiveAuth();
          acquired = false;
          return;
        }
        const db = getClientDb();
        unsubs.push(
          onSnapshot(
            query(collection(db, "attendance"), where("date", "==", today)),
            (snap) => {
              setPunches(snap.docs.map((d) => toPunch(d.id, d.data())));
              setState("live");
            },
            fail,
          ),
          onSnapshot(
            query(collection(db, "smsLog"), where("date", "==", today)),
            (snap) => setSms(snap.docs.map((d) => ({ status: String(d.data().status ?? "") }))),
            fail,
          ),
          onSnapshot(
            doc(db, "bridgeStatus", "main"),
            (snap) => {
              const x = snap.data();
              setBridge({
                loaded: true,
                info: x
                  ? {
                      heartbeat: toDate(x.heartbeat),
                      deviceOnline: x.deviceOnline === true,
                      carrier: typeof x.carrier === "string" && x.carrier ? x.carrier : undefined,
                      gsmSignal: typeof x.gsmSignal === "number" ? x.gsmSignal : undefined,
                    }
                  : null,
              });
            },
            fail,
          ),
        );
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });
    return () => {
      cancelled = true;
      for (const u of unsubs) u();
      if (acquired) releaseLiveAuth();
    };
  }, [today]);

  const kpis = useMemo(() => computeKpis(people, punches, sms), [people, punches, sms]);
  const names = useMemo(() => new Map(people.map((p) => [p.id, p.name])), [people]);
  const feed = useMemo(() => latestPunches(punches, FEED_SIZE), [punches]);
  const pulseKey = feed[0]?.id ?? "none";

  return (
    <div className="space-y-4">
      <p role="status" className="text-sm text-muted-foreground">
        {today} -{" "}
        {state === "live" ? "Live updates on" : state === "connecting" ? "Connecting to live updates..." : null}
      </p>
      {state === "failed" ? (
        <p role="alert" className="rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
          Live updates are unavailable. Showing the last received data; reload the page to refresh.
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-4">
        <KpiCards kpis={kpis} />
        <PresenceGlobe pulseKey={pulseKey} />
      </div>

      {bridge.loaded ? (
        <BridgeStatusChip status={bridge.info} now={now} />
      ) : (
        <p role="status" className="inline-flex rounded-full border border-border px-3 py-1 text-sm text-muted-foreground">
          {state === "failed" ? "Bridge status unavailable" : "Checking bridge..."}
        </p>
      )}

      <section aria-labelledby="feed-heading" className="space-y-2">
        <h2 id="feed-heading" className="text-lg font-semibold">
          Latest punches
        </h2>
        <LiveFeed punches={feed} names={names} tz={tz} />
      </section>
    </div>
  );
}
