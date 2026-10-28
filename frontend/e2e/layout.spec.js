// Layout and interaction details: phone screens, dark mode, keyboard behaviour.
import { expect, newChat, shot, test } from "./helpers.js";

test("phone layout: the menu opens the sidebar and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("/");
  const sidebar = page.locator("aside");
  await expect(page.getByRole("button", { name: "Open conversations" })).toBeVisible();
  await expect(sidebar).not.toBeInViewport();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  await shot(page, "15-mobile-chat");

  await page.getByRole("button", { name: "Open conversations" }).click();
  // Wait for the slide-in animation to finish: the whole sidebar on screen, list loaded.
  await expect(sidebar).toBeInViewport({ ratio: 1 });
  await expect(sidebar.locator("li").first()).toBeVisible();
  await shot(page, "16-mobile-menu-open");
});

test("dark mode follows the system setting", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  // Open a conversation that has messages, so the screenshot shows real content.
  const withMessages = page.locator("aside li").filter({ hasText: /[1-9]\d* messages?/ });
  await withMessages.first().getByRole("button").first().click();
  await expect(page.locator("article").first()).toBeVisible({ timeout: 30_000 });
  const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(background).toBe("rgb(15, 16, 22)"); // --bg in dark mode
  await shot(page, "17-dark-mode");
});

test("keyboard: Shift+Enter adds a line, Enter on empty text sends nothing", async ({ page }) => {
  await page.goto("/");
  // Wait until the page has settled (the input is briefly disabled while the latest
  // conversation loads; keys typed then are dropped, which made this test flaky in CI).
  await newChat(page);
  const box = page.getByLabel(/ask a question/i);
  await expect(box).toBeEnabled();
  await box.fill("first line");
  await box.press("Shift+Enter");
  await box.pressSequentially("second line");
  await expect(box).toHaveValue("first line\nsecond line");

  await box.fill("   ");
  const turns = await page.locator("article").count();
  await box.press("Enter");
  await expect(page.locator("article")).toHaveCount(turns);
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
});
