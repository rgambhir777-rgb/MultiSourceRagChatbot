// Shared E2E helpers and a `test` that fails on any browser console error.
import { test as base, expect } from "@playwright/test";

export const SCREENSHOT_DIR = "e2e-results/screenshots";
const ANSWER_TIMEOUT_MS = 120_000; // real OpenAI answers occasionally take ~25 s

/**
 * `test` with an automatic check: any console error or uncaught exception in the page
 * fails the test, even if every assertion passed.
 */
export const test = base.extend({
  // Console errors a test deliberately causes (e.g. a 422 from a rejected request).
  expectedConsoleErrors: [[], { option: true }],
  consoleErrors: [
    async ({ page, expectedConsoleErrors }, use) => {
      const errors = [];
      page.on("console", (message) => {
        const text = message.text();
        if (message.type() === "error" && !expectedConsoleErrors.some((re) => re.test(text))) {
          errors.push(text);
        }
      });
      page.on("pageerror", (error) => errors.push(error.message));
      await use(errors);
      expect(errors, "browser console errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** Save a named screenshot (also attached to the HTML report). */
export async function shot(page, name, options = {}) {
  const path = `${SCREENSHOT_DIR}/${name}.png`;
  await page.screenshot({ path, ...options });
  await test.info().attach(name, { path, contentType: "image/png" });
}

/** Open the Chat view and start an empty conversation. */
export async function newChat(page) {
  await page.getByRole("button", { name: "Chat", exact: true }).click();
  await page.getByRole("button", { name: "+ New chat" }).click();
  await expect(page.getByRole("heading", { name: "Ask your documents" })).toBeVisible();
}

/** Type a question and press Enter. Returns the article (turn) it creates. */
export async function ask(page, question) {
  const before = await page.locator("article").count();
  const box = page.getByLabel(/ask a question/i);
  await box.fill(question);
  await box.press("Enter");
  const turn = page.locator("article").nth(before);
  await expect(turn.getByText(question, { exact: true })).toBeVisible();
  return turn;
}

/** Wait until a turn has finished (its "x.x s · $y" stats line appears). */
export async function waitForAnswer(turn) {
  await expect(turn.getByText(/\d+\.\d s · \$\d/)).toBeVisible({ timeout: ANSWER_TIMEOUT_MS });
}

/** The text of a turn's answer, without the question. */
export async function answerText(turn) {
  return (await turn.locator("div[aria-live]").innerText()).trim();
}
