import { expect, test } from "@playwright/test";
import { PASSWORD, USERS } from "./fixtures";
import { appAlert, loginAs } from "./helpers";

test.describe("login and sessions", () => {
  test("admin logs in and lands on the dashboard", async ({ page }) => {
    await loginAs(page, "admin");
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  });

  test("a wrong password shows an error and stays on /login", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.admin.email);
    await page.getByLabel("Password").fill(`${PASSWORD}-wrong`);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(appAlert(page)).toContainText("Sign-in failed");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("an account with no role is refused and gets no session", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.norole.email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(appAlert(page)).toContainText("no role");
    await expect(page).toHaveURL(/\/login$/);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("unauthenticated visits are redirected to /login", async ({ page }) => {
    await page.goto("/people");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("sign-out returns to /login and protects the dashboard again", async ({ page }) => {
    await loginAs(page, "admin");
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/);
  });
});
