// Chat: real questions through the real agent (OpenAI), checking what the user sees.
import { answerText, ask, expect, newChat, shot, test, waitForAnswer } from "./helpers.js";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "+ New chat" })).toBeVisible();
});

test("home page shows the sidebar, views and an empty chat", async ({ page }) => {
  await newChat(page);
  await expect(page.getByRole("button", { name: "Knowledge base" })).toBeVisible();
  await expect(page.getByRole("button", { name: "What does error E-207 mean?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeDisabled();
  await shot(page, "01-empty-chat");
});

test("answers a document question with citations, sources and a verified badge", async ({
  page,
}) => {
  await newChat(page);
  const turn = await ask(page, "What does error E-207 mean?");

  // While it works: progress steps and a Stop button.
  await expect(turn.getByRole("list", { name: "Progress" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();
  await shot(page, "02-streaming-progress");

  await waitForAnswer(turn);
  expect(await answerText(turn)).toMatch(/wi-?fi/i);
  await expect(turn.getByText("Verified against sources")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
  await shot(page, "03-answer-verified");

  // Clicking a citation opens the sources and highlights the cited passage.
  await turn
    .getByRole("button", { name: /Show source \d/ })
    .first()
    .click();
  await expect(turn.getByRole("button", { name: /^Sources/ })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(turn.getByText(/orbit_troubleshooting\.pdf, page 1/)).toBeVisible();
  await shot(page, "04-citation-sources-open");

  // The new conversation is listed in the sidebar, titled from the question.
  await expect(
    page.locator("aside").getByRole("button", { name: /^What does error E-207 mean\?/ }),
  ).toBeVisible();
});

test("remembers the conversation for follow-ups, also after a page reload", async ({ page }) => {
  await newChat(page);
  const first = await ask(page, "What does error E-114 mean?");
  await waitForAnswer(first);

  const followUp = await ask(page, "And how do I fix it?");
  await waitForAnswer(followUp);
  expect(await answerText(followUp)).toMatch(/c-wire|adapter|power/i);
  await shot(page, "05-follow-up-memory");

  await page.reload();
  await expect(page.locator("article")).toHaveCount(2);
  await expect(page.getByText("And how do I fix it?", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What does error E-114 mean?" })).toBeVisible();
  await shot(page, "06-after-reload");
});

test("says honestly when the documents don't contain the answer", async ({ page }) => {
  await newChat(page);
  const turn = await ask(page, "What is the capital of France?");
  await waitForAnswer(turn);
  expect(await answerText(turn)).toContain("I couldn't find this in the documents.");
  await expect(turn.getByRole("button", { name: /^Sources/ })).toHaveCount(0);
  await shot(page, "07-not-found");
});

test("replies to a greeting directly, without sources or a badge", async ({ page }) => {
  await newChat(page);
  const turn = await ask(page, "Hi there!");
  await waitForAnswer(turn);
  await expect(turn.getByText(/verified/i)).toHaveCount(0);
  await expect(turn.getByRole("button", { name: /^Sources/ })).toHaveCount(0);
  await shot(page, "08-greeting-direct");
});

test("Stop cancels an answer that is still being written", async ({ page }) => {
  await newChat(page);
  const turn = await ask(
    page,
    "Explain every error code in the troubleshooting guide in detail, with all the steps.",
  );
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(turn.getByText("Stopped.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
  await shot(page, "09-stopped");
});

test("answers questions about code from an indexed GitHub repository", async ({ page }) => {
  await newChat(page);
  const turn = await ask(page, "How do I make a signed token expire with itsdangerous?");
  await waitForAnswer(turn);
  expect(await answerText(turn)).toMatch(/max_age/);
  await expect(turn.locator("pre code").first()).toBeVisible(); // a rendered code block
  await turn.getByRole("button", { name: /^Sources/ }).click();
  await expect(turn.getByText(/pallets\/itsdangerous\//).first()).toBeVisible();
  await shot(page, "10-github-code-answer", { fullPage: true });
});

test("deletes a conversation", async ({ page }) => {
  await newChat(page);
  const turn = await ask(page, "Hello!");
  await waitForAnswer(turn);
  const row = page.locator("aside li").filter({ hasText: "Hello!" }).first();
  await expect(row).toBeVisible();
  const before = await page.locator("aside li").count();

  page.once("dialog", (dialog) => dialog.accept()); // the "Delete this conversation?" prompt
  await row.getByRole("button", { name: /Delete conversation/ }).click();
  await expect(page.locator("aside li")).toHaveCount(before - 1);
});
