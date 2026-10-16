import { describe, expect, it } from "vitest";
import { renderToBuffer } from "@react-pdf/renderer";
import { PersonReportDocument } from "./person-report";

describe("PersonReportDocument", () => {
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
