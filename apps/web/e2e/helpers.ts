import { expect, type Page } from "@playwright/test";
import { PASSWORD, USERS, type Who } from "./fixtures";

/** Logs in through the real login form and asserts the role landing page. */
export async function loginAs(page: Page, who: Exclude<Who, "norole">): Promise<void> {
  const u = USERS[who];
  await page.goto("/login");
  await page.getByLabel("Email").fill(u.email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new RegExp(`${u.home}$`));
}

/** App alerts, excluding Next's route announcer which also has role=alert. */
export function appAlert(page: Page) {
  return page.locator('[role="alert"]:not(#__next-route-announcer__)');
}
