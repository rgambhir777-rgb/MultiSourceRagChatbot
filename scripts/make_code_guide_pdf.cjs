// Rebuild docs/code-guide.pdf from docs/code-guide.html.
//
// It prints the HTML with the headless Chromium that the frontend's Playwright tests already
// use, so no extra tool is needed. Run from the project root (after `npm ci` in frontend/ and
// `npx playwright install chromium` once):
//
//   node scripts/make_code_guide_pdf.cjs
const { createRequire } = require("module");
const path = require("path");
const { pathToFileURL } = require("url");

const ROOT = path.resolve(__dirname, "..");
const HTML = path.join(ROOT, "docs", "code-guide.html");
const PDF = path.join(ROOT, "docs", "code-guide.pdf");

// Load Playwright from frontend/node_modules (that's where it is installed).
const { chromium } = createRequire(path.join(ROOT, "frontend", "package.json"))("@playwright/test");

const FOOTER =
  '<div style="width:100%;font-size:8px;color:#888;padding:0 15mm;display:flex;justify-content:space-between">' +
  '<span>MultiSourceRagChatbot · code guide</span>' +
  '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>';

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(HTML).href);
    await page.pdf({
      path: PDF,
      format: "A4",
      printBackground: true, // keep the coloured boxes and diagrams
      preferCSSPageSize: true, // margins come from @page in the HTML
      displayHeaderFooter: true,
      headerTemplate: "<span></span>",
      footerTemplate: FOOTER,
    });
    console.log(`written ${path.relative(ROOT, PDF)}`);
  } finally {
    await browser.close();
  }
})();
