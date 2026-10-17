import { describe, expect, it, vi } from "vitest";
import type { Session } from "./access";
import {
  addHolidayWith,
  deleteDeviceWith,
  deleteScheduleWith,
  exportBackupWith,
  removeHolidayWith,
  restoreBackupWith,
  saveAppSettingsWith,
  saveBridgeSettingsWith,
  saveDeviceWith,
  updateDeviceWith,
  stripUndefined,
  saveScheduleWith,
  saveSmsSettingsWith,
  MAX_BACKUP_BYTES,
  type SettingsDeps,
} from "./settings";
import { DEFAULT_APP, DEFAULT_BRIDGE, DEFAULT_SMS } from "./settings-defaults";

const admin: Session = { uid: "a", role: "admin" };
const staff: Session = { uid: "s", role: "staff" };

type Store = Map<string, Map<string, Record<string, unknown>>>;

function makeDeps(seed: Store = new Map()) {
  const store = seed;
  const col = (c: string) => {
    let m = store.get(c);
    if (!m) store.set(c, (m = new Map()));
    return m;
  };
  const deps = {
    newId: vi.fn(() => "auto1"),
    set: vi.fn(async (c: string, id: string, data: Record<string, unknown>, opts?: { merge?: boolean }) => {
      const prev = opts?.merge ? (col(c).get(id) ?? {}) : {};
      col(c).set(id, { ...prev, ...data });
    }),
    create: vi.fn(async (c: string, id: string, data: Record<string, unknown>) => {
      if (col(c).has(id)) throw Object.assign(new Error("exists"), { code: 6 });
      col(c).set(id, data);
    }),
    remove: vi.fn(async (c: string, id: string) => void col(c).delete(id)),
    get: vi.fn(async (c: string, id: string) => col(c).get(id) ?? null),
    list: vi.fn(async (c: string) => [...col(c)].map(([id, data]) => ({ id, data }))),
    setBatch: vi.fn(async (items: { collection: string; id: string; data: Record<string, unknown> }[]) => {
      for (const i of items) col(i.collection).set(i.id, i.data);
    }),
  };
  return { deps: deps as SettingsDeps & typeof deps, store };
}

function seedStore(): Store {
  const s: Store = new Map();
  s.set(
    "people",
    new Map([
      [
        "P1",
        {
          name: "Ayesha",
          kind: "student",
          className: "5",
          guardianUids: [],
          deviceEnrolled: true,
          active: true,
          createdAt: new Date("2026-01-02T03:04:05.000Z"),
        },
      ],
    ]),
  );
  s.set(
    "schedules",
    new Map([["s1", { name: "Day", start: "07:45", end: "08:15", graceMin: 5, dismissal: "13:00", appliesTo: ["5"] }]]),
  );
  s.set("holidays", new Map([["2026-12-16", { name: "Victory Day" }]]));
  s.set(
    "devices",
    new Map([["main", { name: "Gate", ip: "192.168.1.201", port: 4370, lastSeen: new Date("2026-01-01T00:00:00.000Z") }]]),
  );
  s.set(
    "settings",
    new Map([
      ["bridge", { ...DEFAULT_BRIDGE }],
      ["sms", { ...DEFAULT_SMS }],
      ["app", { ...DEFAULT_APP }],
    ]),
  );
  return s;
}

const goodSchedule = { name: "Day", start: "07:45", end: "08:15", graceMin: 5, appliesTo: ["5"] };

describe("non-admin is rejected with zero deps calls", () => {
  const calls: [string, (d: SettingsDeps, c: Session | null) => Promise<unknown>][] = [
    ["saveSchedule", (d, c) => saveScheduleWith(d, c, goodSchedule)],
    ["deleteSchedule", (d, c) => deleteScheduleWith(d, c, "s1")],
    ["addHoliday", (d, c) => addHolidayWith(d, c, "2026-12-16", "x")],
    ["removeHoliday", (d, c) => removeHolidayWith(d, c, "2026-12-16")],
    ["saveSmsSettings", (d, c) => saveSmsSettingsWith(d, c, DEFAULT_SMS)],
    ["saveBridgeSettings", (d, c) => saveBridgeSettingsWith(d, c, DEFAULT_BRIDGE)],
    ["saveAppSettings", (d, c) => saveAppSettingsWith(d, c, DEFAULT_APP)],
    ["saveDevice", (d, c) => saveDeviceWith(d, c, { id: "m", name: "n", ip: "1.2.3.4", port: 4370 })],
    ["updateDevice", (d, c) => updateDeviceWith(d, c, { id: "m", name: "n", ip: "1.2.3.4", port: 4370 })],
    ["deleteDevice", (d, c) => deleteDeviceWith(d, c, "m")],
    ["exportBackup", (d, c) => exportBackupWith(d, c)],
    ["restoreBackup", (d, c) => restoreBackupWith(d, c, "{}")],
  ];
  for (const [name, fn] of calls) {
    for (const [who, caller] of [["staff", staff], ["anonymous", null]] as const) {
      it(`${name} (${who})`, async () => {
        const { deps } = makeDeps();
        await expect(fn(deps, caller)).rejects.toThrow("Forbidden: admin only");
        for (const f of Object.values(deps)) if (vi.isMockFunction(f)) expect(f).not.toHaveBeenCalled();
      });
    }
  }
});

describe("saveSchedule", () => {
  it("rejects a non HH:mm start", async () => {
    const { deps } = makeDeps();
    const r = await saveScheduleWith(deps, admin, { ...goodSchedule, start: "8am" });
    expect(r.ok).toBe(false);
    expect(deps.set).not.toHaveBeenCalled();
  });
  it("rejects dismissal 25:00", async () => {
    const { deps } = makeDeps();
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, dismissal: "25:00" })).ok).toBe(false);
  });
  it("rejects dismissal not after end", async () => {
    const { deps } = makeDeps();
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, dismissal: "08:15" })).ok).toBe(false);
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, dismissal: "08:00" })).ok).toBe(false);
  });
  it("requires dismissal later than end plus grace", async () => {
    const { deps } = makeDeps();
    const r = await saveScheduleWith(deps, admin, { ...goodSchedule, dismissal: "08:20" });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/grace/);
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, dismissal: "08:21" })).ok).toBe(true);
  });
  it("rejects empty appliesTo and negative grace", async () => {
    const { deps } = makeDeps();
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, appliesTo: [] })).ok).toBe(false);
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, appliesTo: ["  "] })).ok).toBe(false);
    expect((await saveScheduleWith(deps, admin, { ...goodSchedule, graceMin: -1 })).ok).toBe(false);
  });
  it("trims and de-duplicates appliesTo and generates an id", async () => {
    const { deps, store } = makeDeps();
    const r = await saveScheduleWith(deps, admin, {
      ...goodSchedule,
      dismissal: "13:00",
      appliesTo: [" 5 ", "5", "6", " 6"],
    });
    expect(r.ok).toBe(true);
    expect(store.get("schedules")?.get("auto1")?.appliesTo).toEqual(["5", "6"]);
  });
  it("uses the given id and drops an empty dismissal", async () => {
    const { deps, store } = makeDeps();
    await saveScheduleWith(deps, admin, { ...goodSchedule, id: "s9", dismissal: "" });
    const doc = store.get("schedules")?.get("s9");
    expect(doc).toBeDefined();
    expect("dismissal" in (doc ?? {})).toBe(false);
  });
});

describe("holidays", () => {
  it("rejects a non-existent calendar date", async () => {
    const { deps } = makeDeps();
    expect((await addHolidayWith(deps, admin, "2026-02-30", "x")).ok).toBe(false);
    expect((await addHolidayWith(deps, admin, "2026-12-16", "  ")).ok).toBe(false);
    expect(deps.set).not.toHaveBeenCalled();
  });
  it("writes holidays/{date}", async () => {
    const { deps, store } = makeDeps();
    expect((await addHolidayWith(deps, admin, "2026-12-16", " Victory Day ")).ok).toBe(true);
    expect(store.get("holidays")?.get("2026-12-16")).toEqual({ name: "Victory Day" });
    expect((await removeHolidayWith(deps, admin, "2026-12-16")).ok).toBe(true);
    expect(store.get("holidays")?.has("2026-12-16")).toBe(false);
  });
});

describe("saveSmsSettings", () => {
  const keys = ["normalTemplate", "lateTemplate", "earlyLeaveTemplate", "absentTemplate", "summaryTemplate"] as const;
  for (const k of keys) {
    it(`rejects {bogus} in ${k}`, async () => {
      const { deps } = makeDeps();
      const r = await saveSmsSettingsWith(deps, admin, { ...DEFAULT_SMS, [k]: "Hi {bogus}" });
      expect(r.ok).toBe(false);
      expect(deps.set).not.toHaveBeenCalled();
    });
  }
  for (const k of keys) {
    for (const bad of ["Dear {name, your child", "Bye :-}", "Hi {}", "Hi {0}", "{{name}"]) {
      it(`rejects the unbalanced template ${JSON.stringify(bad)} in ${k}`, async () => {
        const { deps } = makeDeps();
        const r = await saveSmsSettingsWith(deps, admin, { ...DEFAULT_SMS, [k]: bad });
        expect(r.ok).toBe(false);
        expect(deps.set).not.toHaveBeenCalled();
      });
    }
  }
  it("accepts doubled literal braces", async () => {
    const { deps } = makeDeps();
    const r = await saveSmsSettingsWith(deps, admin, { ...DEFAULT_SMS, normalTemplate: "{{Note}} {name} at {time}" });
    expect(r.ok).toBe(true);
  });
  it("rejects more than 2 admin phones", async () => {
    const { deps } = makeDeps();
    expect((await saveSmsSettingsWith(deps, admin, { ...DEFAULT_SMS, adminPhones: ["1", "2", "3"] })).ok).toBe(false);
  });
  it("writes exactly the keys the bridge reads", async () => {
    const { deps } = makeDeps();
    await saveSmsSettingsWith(deps, admin, DEFAULT_SMS);
    const written = deps.set.mock.calls[0]?.[2] as Record<string, unknown>;
    // apps/bridge/src/bridge/firestore_store.py get_sms_settings (+ adminPhones)
    expect(Object.keys(written).sort()).toEqual(
      [
        "normalTemplate",
        "lateTemplate",
        "earlyLeaveTemplate",
        "smsEnabled",
        "earlyLeaveEnabled",
        "absentEnabled",
        "summaryEnabled",
        "summaryTime",
        "absentTemplate",
        "summaryTemplate",
        "adminPhones",
      ].sort(),
    );
    expect(deps.set.mock.calls[0]?.[0]).toBe("settings");
    expect(deps.set.mock.calls[0]?.[1]).toBe("sms");
  });
});

describe("saveBridgeSettings", () => {
  it("writes exactly the keys the bridge reads", async () => {
    const { deps } = makeDeps();
    expect((await saveBridgeSettingsWith(deps, admin, DEFAULT_BRIDGE)).ok).toBe(true);
    const written = deps.set.mock.calls[0]?.[2] as Record<string, unknown>;
    // apps/bridge/src/bridge/firestore_store.py get_bridge_settings
    expect(Object.keys(written).sort()).toEqual(
      ["pollIntervalSec", "zkTimeoutSec", "gsmPort", "gsmBaud", "staleSmsWindowMin", "ussdCode"].sort(),
    );
  });
  it("rejects a non-positive poll interval", async () => {
    const { deps } = makeDeps();
    expect((await saveBridgeSettingsWith(deps, admin, { ...DEFAULT_BRIDGE, pollIntervalSec: 0 })).ok).toBe(false);
  });
});

describe("saveAppSettings", () => {
  it("rejects an invalid time zone", async () => {
    const { deps } = makeDeps();
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, timeZone: "Mars/Olympus" })).ok).toBe(false);
  });
  it("accepts Asia/Dhaka and writes the expected keys", async () => {
    const { deps } = makeDeps();
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, timeZone: "Asia/Dhaka" })).ok).toBe(true);
    // The bridge reads only settings/app.timeZone (firestore_store.py get_time_zone and
    // service.py _load_time_zone use dict .get), so extra keys such as weekendDays are ignored.
    expect(Object.keys(deps.set.mock.calls[0]?.[2] as object).sort()).toEqual([
      "notificationSound",
      "orgName",
      "timeZone",
      "weekendDays",
    ]);
  });
  it("stores the canonical time zone name", async () => {
    const { deps, store } = makeDeps();
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, timeZone: "asia/dhaka" })).ok).toBe(true);
    expect(store.get("settings")?.get("app")?.timeZone).toBe("Asia/Dhaka");
  });
  it("stores weekendDays sorted and rejects invalid ones", async () => {
    const { deps, store } = makeDeps();
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, weekendDays: [6, 5] })).ok).toBe(true);
    expect(store.get("settings")?.get("app")?.weekendDays).toEqual([5, 6]);
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, weekendDays: [5, 5] })).ok).toBe(false);
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, weekendDays: [7] })).ok).toBe(false);
  });
  it("requires an org name", async () => {
    const { deps } = makeDeps();
    expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, orgName: " " })).ok).toBe(false);
  });
  // The bridge loads the zone with Python's ZoneInfo: offsets and GMT+N spellings would
  // crash it, so only IANA names (plus UTC) are accepted.
  for (const bad of ["+06:00", "GMT+6", "-0300", "", "Asia/Nowhere"]) {
    it(`rejects the non-IANA zone ${JSON.stringify(bad)}`, async () => {
      const { deps } = makeDeps();
      expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, timeZone: bad })).ok).toBe(false);
      expect(deps.set).not.toHaveBeenCalled();
    });
  }
  for (const [input, stored] of [
    ["UTC", "UTC"],
    ["utc", "UTC"],
    ["Etc/UTC", "UTC"],
    ["America/New_York", "America/New_York"],
    ["europe/london", "Europe/London"],
  ] as const) {
    it(`accepts ${input} and stores ${stored}`, async () => {
      const { deps, store } = makeDeps();
      expect((await saveAppSettingsWith(deps, admin, { ...DEFAULT_APP, timeZone: input })).ok).toBe(true);
      expect(store.get("settings")?.get("app")?.timeZone).toBe(stored);
    });
  }
});

describe("saveDevice", () => {
  const good = { id: "main", name: "Gate", ip: "192.168.1.201", port: 4370 };
  it("rejects bad ports", async () => {
    const { deps } = makeDeps();
    expect((await saveDeviceWith(deps, admin, { ...good, port: 0 })).ok).toBe(false);
    expect((await saveDeviceWith(deps, admin, { ...good, port: 70000 })).ok).toBe(false);
  });
  it("rejects bad ips", async () => {
    const { deps } = makeDeps();
    for (const ip of ["999.1.1.1", "1.2.3", "bad host", "-x.com", "", "a..b"]) {
      expect((await saveDeviceWith(deps, admin, { ...good, ip })).ok, ip).toBe(false);
    }
  });
  it("creates a device with exactly the keys the bridge reads, create-only", async () => {
    const { deps, store } = makeDeps();
    expect((await saveDeviceWith(deps, admin, { ...good, ip: "zk-gate.local" })).ok).toBe(true);
    expect(store.get("devices")?.get("main")?.ip).toBe("zk-gate.local");
    // apps/bridge list_devices reads name, ip, port (id = doc id)
    expect(Object.keys(deps.create.mock.calls[0]?.[2] as object).sort()).toEqual(["ip", "name", "port"]);
    const again = await saveDeviceWith(deps, admin, good);
    expect(again.ok).toBe(false);
    if (!again.ok) expect(again.error).toMatch(/already exists/);
  });
  it("updates an existing device keeping lastSeen, and refuses a missing one", async () => {
    const { deps, store } = makeDeps(seedStore());
    expect((await updateDeviceWith(deps, admin, { ...good, ip: "zk-gate.local" })).ok).toBe(true);
    const doc = store.get("devices")?.get("main");
    expect(doc?.ip).toBe("zk-gate.local");
    expect(doc?.lastSeen).toEqual(new Date("2026-01-01T00:00:00.000Z"));
    expect(deps.set.mock.calls[0]?.[3]).toEqual({ merge: true });
    expect((await updateDeviceWith(deps, admin, { ...good, id: "nope" })).ok).toBe(false);
  });
  it("deletes a device", async () => {
    const { deps, store } = makeDeps(seedStore());
    expect((await deleteDeviceWith(deps, admin, "main")).ok).toBe(true);
    expect(store.get("devices")?.size).toBe(0);
  });
});

describe("backup", () => {
  it("round trips through export and restore without changing data", async () => {
    const { deps, store } = makeDeps(seedStore());
    const before = structuredClone(store);
    const json = await exportBackupWith(deps, admin);
    const parsed = JSON.parse(json);
    expect(parsed.version).toBe(1);
    expect(parsed.people[0].createdAt).toBe("2026-01-02T03:04:05.000Z");
    const r = await restoreBackupWith(deps, admin, json);
    expect(r).toEqual({ ok: true, restored: { people: 1, schedules: 1, holidays: 1, devices: 1, settings: 3 } });
    expect(store).toEqual(before);
  });

  it("restores into an empty store and converts dates back", async () => {
    const src = makeDeps(seedStore());
    const json = await exportBackupWith(src.deps, admin);
    const dst = makeDeps();
    expect((await restoreBackupWith(dst.deps, admin, json)).ok).toBe(true);
    expect(dst.store.get("people")?.get("P1")?.createdAt).toEqual(new Date("2026-01-02T03:04:05.000Z"));
    expect(dst.store.get("settings")?.get("sms")).toEqual(DEFAULT_SMS);
  });

  it("writes nothing and reports problems when one person is invalid", async () => {
    const src = makeDeps(seedStore());
    const b = JSON.parse(await exportBackupWith(src.deps, admin));
    b.people.push({
      id: "P2",
      name: "Bad",
      kind: "alien",
      deviceEnrolled: true,
      active: true,
      createdAt: "2026-01-01T00:00:00.000Z",
    });
    const dst = makeDeps();
    const r = await restoreBackupWith(dst.deps, admin, JSON.stringify(b));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toContain("people/P2");
    expect(dst.deps.setBatch).not.toHaveBeenCalled();
    expect(dst.deps.set).not.toHaveBeenCalled();
  });

  it("reports at most 10 problems", async () => {
    const b = { version: 1, people: Array.from({ length: 15 }, (_, i) => ({ id: `P${i}`, name: 1 })) };
    const { deps } = makeDeps();
    const r = await restoreBackupWith(deps, admin, JSON.stringify(b));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.split("\n").filter((l) => l.startsWith("people/")).length).toBe(10);
  });

  it("rejects a version mismatch and bad JSON", async () => {
    const { deps } = makeDeps();
    const r = await restoreBackupWith(deps, admin, JSON.stringify({ version: 2 }));
    expect(r.ok).toBe(false);
    expect((await restoreBackupWith(deps, admin, "not json")).ok).toBe(false);
    expect(deps.setBatch).not.toHaveBeenCalled();
  });

  it("rejects oversized input before parsing", async () => {
    const { deps } = makeDeps();
    const r = await restoreBackupWith(deps, admin, " ".repeat(MAX_BACKUP_BYTES + 1));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/too large/i);
  });

  it("writes in batches of 400 and never deletes", async () => {
    const people = Array.from({ length: 850 }, (_, i) => ({
      id: `P${i}`,
      name: "N",
      kind: "staff",
      deviceEnrolled: false,
      active: true,
      createdAt: "2026-01-01T00:00:00.000Z",
    }));
    const { deps } = makeDeps();
    const r = await restoreBackupWith(deps, admin, JSON.stringify({ version: 1, people }));
    expect(r.ok).toBe(true);
    expect(deps.setBatch.mock.calls.map((c) => c[0].length)).toEqual([400, 400, 50]);
    expect(deps.remove).not.toHaveBeenCalled();
  });
});

describe("stripUndefined", () => {
  it("removes undefined recursively, keeps Dates, null and arrays", () => {
    const d = new Date("2026-01-01T00:00:00.000Z");
    expect(stripUndefined({ a: undefined, b: { c: undefined, d: 1, e: d }, f: [1, { g: undefined, h: null }] })).toEqual({
      b: { d: 1, e: d },
      f: [1, { h: null }],
    });
  });
});

describe("restore hardening", () => {
  const person = {
    id: "P1",
    name: "A",
    kind: "student",
    deviceEnrolled: true,
    active: true,
    createdAt: "2026-01-02T03:04:05.000Z",
  };

  it("keeps unknown fields such as the legacy map through a round trip", async () => {
    const seed = seedStore();
    const p = seed.get("people")?.get("P1") as Record<string, unknown>;
    p.legacy = { oldId: 7, nested: { a: 1 } };
    p.managerId = "M1";
    const { deps, store } = makeDeps(seed);
    const before = structuredClone(store);
    const json = await exportBackupWith(deps, admin);
    expect((await restoreBackupWith(deps, admin, json)).ok).toBe(true);
    expect(store).toEqual(before);
    expect(store.get("people")?.get("P1")?.legacy).toEqual({ oldId: 7, nested: { a: 1 } });
  });

  it("restores a schedule with dismissal empty or null, never writing undefined", async () => {
    const schedules = [
      { id: "a", name: "A", start: "07:00", end: "08:00", graceMin: 0, dismissal: "", appliesTo: ["1"] },
      { id: "b", name: "B", start: "07:00", end: "08:00", graceMin: 0, dismissal: null, appliesTo: ["1"] },
    ];
    const { deps, store } = makeDeps();
    expect((await restoreBackupWith(deps, admin, JSON.stringify({ version: 1, schedules }))).ok).toBe(true);
    for (const id of ["a", "b"]) {
      const doc = store.get("schedules")?.get(id) ?? {};
      expect("dismissal" in doc).toBe(false);
      expect(Object.values(doc).includes(undefined)).toBe(false);
    }
  });

  it("reports honest partial failure and stops after the failing batch", async () => {
    const people = Array.from({ length: 850 }, (_, i) => ({ ...person, id: `P${i}` }));
    const { deps } = makeDeps();
    let n = 0;
    deps.setBatch.mockImplementation(async () => {
      n++;
      if (n === 2) throw new Error("boom");
    });
    const r = await restoreBackupWith(deps, admin, JSON.stringify({ version: 1, people }));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toBe("Restore failed after 400 of 850 documents were written: boom");
    expect(deps.setBatch).toHaveBeenCalledTimes(2);
  });

  it("rejects non-ISO dates", async () => {
    const { deps } = makeDeps();
    const r = await restoreBackupWith(deps, admin, JSON.stringify({ version: 1, people: [{ ...person, createdAt: "2026" }] }));
    expect(r.ok).toBe(false);
    expect(deps.setBatch).not.toHaveBeenCalled();
  });

  it("reports duplicate ids within a collection", async () => {
    const { deps } = makeDeps();
    const r = await restoreBackupWith(deps, admin, JSON.stringify({ version: 1, people: [person, person] }));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/people\/P1: duplicate id/);
    expect(deps.setBatch).not.toHaveBeenCalled();
  });
});
