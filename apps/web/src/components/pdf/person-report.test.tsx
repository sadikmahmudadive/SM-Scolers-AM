import { describe, expect, it } from "vitest";
import { renderToBuffer } from "@react-pdf/renderer";
import { PersonReportDocument } from "./person-report";

const props = (name: string) => ({
  orgName: "Org",
  person: { id: "1", name, kind: "student" },
  range: { from: "2026-01-01", to: "2026-01-02" },
  report: { days: [], summary: { present: 0, late: 0, earlyLeave: 0, punches: 0, absent: 0 } },
});

describe("PersonReportDocument", () => {
  it("does not throw for Bengali names", async () => {
    const buf = await renderToBuffer(PersonReportDocument(props(String.fromCodePoint(0x986, 0x9b0, 0x9bf, 0x9ab))));
    expect(buf.subarray(0, 4).toString()).toBe("%PDF");
  }, 30000);

  it("renders a PDF buffer", async () => {
    const buf = await renderToBuffer(
      PersonReportDocument({
        orgName: "Org",
        person: { id: "1", name: "A", kind: "student", className: "Ten", section: "A", phone: "01" },
        range: { from: "2026-01-01", to: "2026-01-02" },
        report: {
          days: [
            { date: "2026-01-01", first: "09:00", last: "15:00", directions: "in, out", late: true, earlyLeave: false, punches: 2, absent: false },
          ],
          summary: { present: 1, late: 1, earlyLeave: 0, punches: 2, absent: 0 },
        },
      }),
    );
    expect(buf.subarray(0, 4).toString()).toBe("%PDF");
  }, 30000);
});
