import { expect, test } from "@playwright/test";
import { loginAs } from "./helpers";

test.describe("role scoping", () => {
  test("staff is redirected from /dashboard to /me and sees only their own data", async ({ page }) => {
    await loginAs(page, "staff");
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/me$/);
    await expect(page.getByRole("heading", { name: "Staff Self" })).toBeVisible();
    await expect(page.getByText("Other Child")).toHaveCount(0);
    await expect(page.getByText("Rahim Uddin")).toHaveCount(0);
  });

  test("a manager sees only their own team", async ({ page }) => {
    await loginAs(page, "manager");
    await expect(page.getByRole("link", { name: "Rahim Uddin" })).toBeVisible();
    await expect(page.getByText("Staff Self")).toHaveCount(0);
    await expect(page.getByText("Ayesha Rahman")).toHaveCount(0);
    await expect(page.getByText("Other Child")).toHaveCount(0);
  });

  test("a guardian sees only their linked child, even when tampering with the URL", async ({ page }) => {
    await loginAs(page, "guardian");
    await expect(page.getByRole("link", { name: "Ayesha Rahman" })).toBeVisible();
    await expect(page.getByText("Other Child")).toHaveCount(0);

    await page.goto("/children?child=202");
    await expect(page.getByRole("link", { name: "Ayesha Rahman" })).toBeVisible();
    await expect(page.getByText("Other Child")).toHaveCount(0);
  });

  test("a guardian is redirected away from /team and /people", async ({ page }) => {
    await loginAs(page, "guardian");
    await page.goto("/team");
    await expect(page).toHaveURL(/\/children$/);
    await page.goto("/people");
    await expect(page).toHaveURL(/\/children$/);
  });

  test("staff cannot fetch a person report", async ({ page }) => {
    await loginAs(page, "staff");
    const res = await page.request.get("/api/reports/person/100");
    expect(res.status()).toBe(403);
  });
});
