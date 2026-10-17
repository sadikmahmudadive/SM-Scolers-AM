import Link from "next/link";
import { COLLECTIONS, type AppSettings, type BridgeSettings, type SmsSettings } from "@hrm/shared";
import { Backup } from "@/components/settings/backup";
import { BridgeSettingsForm } from "@/components/settings/bridge-settings";
import { Devices, type DeviceRow } from "@/components/settings/devices";
import { GeneralSettings } from "@/components/settings/general";
import { GsmTools } from "@/components/settings/gsm-tools";
import { Holidays, type HolidayRow } from "@/components/settings/holidays";
import { Schedules, type ScheduleRow } from "@/components/settings/schedules";
import { SmsTemplates } from "@/components/settings/sms-templates";
import { getAdminDb } from "@/lib/firebase-admin";
import { requireRole } from "@/lib/session";
import { DEFAULT_APP, DEFAULT_BRIDGE, DEFAULT_SMS } from "@/lib/settings-defaults";

const TABS = [
  { key: "schedules", label: "Schedules" },
  { key: "holidays", label: "Holidays" },
  { key: "sms", label: "SMS" },
  { key: "bridge", label: "Bridge" },
  { key: "devices", label: "Devices" },
  { key: "gsm", label: "GSM tools" },
  { key: "backup", label: "Configuration backup" },
  { key: "general", label: "General" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pickTab(v: string | string[] | undefined): TabKey {
  const s = Array.isArray(v) ? v[0] : v;
  return TABS.find((t) => t.key === s)?.key ?? "schedules";
}

/** Stored settings over defaults; unknown/mistyped stored fields fall back to the default. */
function withDefaults<T extends object>(defaults: T, stored: Record<string, unknown> | undefined): T {
  const out = { ...defaults } as Record<string, unknown>;
  for (const [k, d] of Object.entries(defaults)) {
    const v = stored?.[k];
    if (v !== undefined && v !== null && typeof v === typeof d && Array.isArray(v) === Array.isArray(d)) out[k] = v;
  }
  return out as T;
}

async function settingsDoc(name: "bridge" | "sms" | "app"): Promise<Record<string, unknown> | undefined> {
  const snap = await getAdminDb().collection(COLLECTIONS.settings).doc(name).get();
  return snap.exists ? snap.data() : undefined;
}

async function loadSchedules(): Promise<ScheduleRow[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.schedules).get();
  return snap.docs
    .map((d) => {
      const x = d.data();
      return {
        id: d.id,
        name: String(x.name ?? ""),
        start: String(x.start ?? ""),
        end: String(x.end ?? ""),
        graceMin: Number(x.graceMin ?? 0),
        dismissal: typeof x.dismissal === "string" ? x.dismissal : undefined,
        appliesTo: Array.isArray(x.appliesTo) ? x.appliesTo.map(String) : [],
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

async function loadTargets(): Promise<string[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.people).select("className", "departmentId").get();
  const set = new Set<string>();
  for (const d of snap.docs) {
    const x = d.data();
    if (x.className) set.add(String(x.className));
    if (x.departmentId) set.add(String(x.departmentId));
  }
  return [...set].sort();
}

async function loadHolidays(): Promise<HolidayRow[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.holidays).get();
  return snap.docs.map((d) => ({ date: d.id, name: String(d.data().name ?? "") })).sort((a, b) => a.date.localeCompare(b.date));
}

async function loadDevices(): Promise<DeviceRow[]> {
  const snap = await getAdminDb().collection(COLLECTIONS.devices).get();
  return snap.docs
    .map((d) => {
      const x = d.data();
      const seen = x.lastSeen && typeof x.lastSeen.toDate === "function" ? (x.lastSeen.toDate() as Date) : null;
      return {
        id: d.id,
        name: String(x.name ?? d.id),
        ip: String(x.ip ?? ""),
        port: Number(x.port ?? 4370),
        lastSeen: seen ? `${seen.toISOString().replace("T", " ").slice(0, 16)} UTC` : undefined,
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

export default async function SettingsPage({ searchParams }: { searchParams: SearchParams }) {
  await requireRole("admin");
  const tab = pickTab((await searchParams).tab);

  let body: React.ReactNode;
  switch (tab) {
    case "schedules": {
      const [schedules, targets] = await Promise.all([loadSchedules(), loadTargets()]);
      body = <Schedules schedules={schedules} targets={targets} />;
      break;
    }
    case "holidays":
      body = <Holidays holidays={await loadHolidays()} />;
      break;
    case "sms":
      body = <SmsTemplates initial={withDefaults<SmsSettings>(DEFAULT_SMS, await settingsDoc("sms"))} />;
      break;
    case "bridge":
      body = (
        <BridgeSettingsForm initial={withDefaults<BridgeSettings>(DEFAULT_BRIDGE, await settingsDoc("bridge"))} />
      );
      break;
    case "devices":
      body = <Devices devices={await loadDevices()} />;
      break;
    case "gsm": {
      const bridge = withDefaults<BridgeSettings>(DEFAULT_BRIDGE, await settingsDoc("bridge"));
      body = <GsmTools ussdCode={bridge.ussdCode} />;
      break;
    }
    case "backup":
      body = <Backup />;
      break;
    case "general":
      body = <GeneralSettings initial={withDefaults<AppSettings>(DEFAULT_APP, await settingsDoc("app"))} />;
      break;
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <nav aria-label="Settings sections" className="flex flex-wrap gap-1 border-b border-border pb-2">
        {TABS.map((t) => (
          <Link
            key={t.key}
            href={`/settings?tab=${t.key}`}
            aria-current={t.key === tab ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground ${
              t.key === tab ? "bg-accent font-medium text-accent-foreground" : ""
            }`}
          >
            {t.label}
          </Link>
        ))}
      </nav>
      <div>{body}</div>
    </main>
  );
}
