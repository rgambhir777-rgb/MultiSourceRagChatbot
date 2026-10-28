// Knowledge base: browse what's indexed, add a document, and use it in the chat.
import { answerText, ask, expect, newChat, shot, test, waitForAnswer } from "./helpers.js";

// A made-up fact that cannot be in any other document, so the answer must come from the upload.
export const UPLOAD_NAME = "e2e-upload-test.md";
const UPLOAD_CONTENT = [
  "# Lumen test lab",
  "",
  "The Lumen test lab's secret code word for the Orbit T2 calibration rig is AURORA-42.",
  "The rig is serviced every second Thursday.",
].join("\n");

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Knowledge base" }).click();
  await expect(page.getByRole("heading", { name: "Knowledge base" })).toBeVisible();
});

test("lists indexed documents and recent jobs", async ({ page }) => {
  await expect(page.locator("tbody tr").first()).toBeVisible();
  expect(await page.locator("tbody tr").count()).toBeGreaterThanOrEqual(4);
  await expect(page.getByRole("cell", { name: "orbit_handbook.md" })).toBeVisible();
  await shot(page, "11-knowledge-base");
});

test("uploads a document, indexes it, then answers from it", async ({ page }) => {
  await page.locator('input[type="file"]').setInputFiles({
    name: UPLOAD_NAME,
    mimeType: "text/markdown",
    buffer: Buffer.from(UPLOAD_CONTENT),
  });
  const job = page.locator("main li").filter({ hasText: UPLOAD_NAME }).first();
  await expect(job.getByText("Done")).toBeVisible({ timeout: 60_000 });
  await expect(job.getByText(/1 (indexed|reindexed|skipped)/)).toBeVisible();
  await expect(page.getByRole("cell", { name: UPLOAD_NAME })).toBeVisible();
  await shot(page, "12-upload-indexed");

  await newChat(page);
  const turn = await ask(page, "What is the secret code word of the Lumen test lab?");
  await waitForAnswer(turn);
  expect(await answerText(turn)).toContain("AURORA-42");
  await turn.getByRole("button", { name: /^Sources/ }).click();
  await expect(turn.getByText(new RegExp(UPLOAD_NAME.replace(".", "\\.")))).toBeVisible();
  await shot(page, "13-answer-from-upload");
});

test.describe("validation", () => {
  // The browser logs the deliberately rejected request (HTTP 422) as a console error.
  test.use({ expectedConsoleErrors: [/status of 422/] });

  test("rejects unsupported files and non-GitHub URLs with clear messages", async ({ page }) => {
    await page.locator('input[type="file"]').setInputFiles({
      name: "data.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("a,b\n1,2\n"),
    });
    await expect(page.getByRole("alert")).toContainText("data.csv: use .pdf, .md, .txt, .docx");

    // A newer error must replace the older one on screen.
    await page.getByLabel("GitHub repository URL").fill("https://gitlab.com/owner/repo");
    await page.getByRole("button", { name: "Add" }).click();
    await expect(page.getByRole("alert")).toContainText("only public GitHub repository URLs");
    await shot(page, "14-validation-errors");
  });
});
