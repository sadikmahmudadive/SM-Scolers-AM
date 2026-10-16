import { expect, test, type Page } from "@playwright/test";
import { Timestamp } from "firebase-admin/firestore";
import { emulatorDb } from "./emulator";
import { dhakaDate, PEOPLE, punchDocId, TIME_ZONE } from "./fixtures";
import { loginAs } from "./helpers";

const board = (page: Page, title: "Present" | "Late" | "Absent") =>
  page.locator("section").filter({ has: page.getByRole("heading", { name: new RegExp(`^${title} \\(`) }) });

test.describe("attendance (admin)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
  });

  test("seeded punches appear for the seeded week and can be filtered by person", async ({ page }) => {
    await page.goto(`/attendance?from=${dhakaDate(-6)}&to=${dhakaDate()}`);
    await expect(page.getByText(/\d+ records?/)).toBeVisible();
    await expect(page.getByRole("cell", { name: /Rahim Uddin/ }).first()).toBeVisible();
    await expect(page.getByRole("cell", { name: /Other Child/ }).first()).toBeVisible();

    await page.getByLabel("Person ID").fill(PEOPLE.other.id);
    await page.getByRole("button", { name: "Filter" }).click();
    await expect(page).toHaveURL(/person=202/);
    await expect(page.getByRole("cell", { name: /Other Child/ }).first()).toBeVisible();
    await expect(page.getByRole("cell", { name: /Rahim Uddin/ })).toHaveCount(0);
    await expect(page.getByText("6 records")).toBeVisible();
  });

  test("the today board shows Ayesha late and Other Child absent, then updates live", async ({ page }) => {
    await page.goto("/today");
    await expect(page.getByRole("status")).toContainText("Live updates on");
    await expect(board(page, "Late").getByText("Ayesha Rahman")).toBeVisible();
    await expect(board(page, "Absent").getByText("Other Child")).toBeVisible();

    // LIVE UPDATE: write a punch through the Admin SDK; the open page must move the person without a reload.
    const now = new Date();
    const today = dhakaDate(0, now);
    const hhmm = new Intl.DateTimeFormat("en-GB", {
      timeZone: TIME_ZONE,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(now);
    await emulatorDb()
      .collection("attendance")
      .doc(punchDocId(PEOPLE.other.id, today, hhmm))
      .set({
        personId: PEOPLE.other.id,
        ts: Timestamp.fromDate(now),
        date: today,
        status: "check-in",
        direction: "in",
        deviceId: "dev1",
        late: false,
        earlyLeave: false,
      });
    await expect(board(page, "Present").getByText("Other Child")).toBeVisible({ timeout: 10_000 });
    await expect(board(page, "Absent").getByText("Other Child")).toHaveCount(0);
  });
});
