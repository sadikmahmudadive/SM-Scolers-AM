import { expect, test, type Page } from "@playwright/test";
import { appAlert, loginAs } from "./helpers";

async function addPerson(page: Page): Promise<void> {
  await page.goto("/people/new");
  await page.getByLabel("Device user ID").fill("301");
  await page.getByLabel("Name").fill("E2E Person");
  await page.getByLabel("Kind").selectOption("student");
  await page.getByRole("button", { name: "Add person" }).click();
}

test.describe.serial("people management (admin)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
  });

  test("adds a person through the form and lists it", async ({ page }) => {
    await addPerson(page);
    await expect(page).toHaveURL(/\/people$/);
    await expect(page.getByRole("link", { name: "E2E Person" })).toBeVisible();
  });

  test("search filters the table", async ({ page }) => {
    await page.goto("/people");
    await expect(page.getByRole("link", { name: "Rahim Uddin" })).toBeVisible();
    await page.getByRole("textbox", { name: "Search" }).fill("E2E");
    await page.getByRole("button", { name: "Filter" }).click();
    await expect(page).toHaveURL(/q=E2E/);
    await expect(page.getByRole("link", { name: "E2E Person" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Rahim Uddin" })).toHaveCount(0);
  });

  test("a duplicate id shows the error", async ({ page }) => {
    await addPerson(page);
    await expect(appAlert(page)).toContainText("already exists");
    await expect(page).toHaveURL(/\/people\/new$/);
  });

  test("CSV import reports the bad row and imports the good one", async ({ page }) => {
    await page.goto("/people");
    await page.getByRole("button", { name: "Import CSV" }).click();
    const csv = "id,name,kind\nbad/id,Bad Row,student\n401,Csv Person,teacher\n";
    await page.getByLabel("CSV file").setInputFiles({ name: "people.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
    const report = page.getByRole("region", { name: "CSV import" });
    await expect(report).toContainText("Imported 1 person");
    await expect(report).toContainText("1 row skipped");
    await expect(report).toContainText("Line 2");
    await expect(report).toContainText("Invalid id");
    await page.goto("/people?q=Csv");
    await expect(page.getByRole("link", { name: "Csv Person" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Bad Row" })).toHaveCount(0);
  });
});
