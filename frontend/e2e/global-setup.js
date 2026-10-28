// Before any E2E test: make sure the backend is up, so failures mean "the app is broken",
// not "you forgot to start the API". Also remember which conversations already exist, so
// global-teardown can remove only the ones the tests create.
import { mkdirSync, writeFileSync } from "node:fs";

export const API = "http://127.0.0.1:8000";
export const BEFORE_FILE = "e2e-results/sessions-before.json";

export default async function globalSetup() {
  let body;
  try {
    const response = await fetch(`${API}/ready`, { signal: AbortSignal.timeout(20_000) });
    body = await response.json();
  } catch {
    throw new Error(
      `The API is not reachable at ${API}. Start it first:\n` +
        "  docker compose up -d\n  uvicorn app.main:create_app --factory",
    );
  }
  if (body.status !== "ok") {
    const failing = Object.entries(body.checks)
      .filter(([, check]) => !check.ok)
      .map(([name, check]) => `${name}: ${check.detail}`);
    throw new Error(`The API is not ready:\n  ${failing.join("\n  ")}`);
  }

  const sessions = await (await fetch(`${API}/api/sessions?limit=200`)).json();
  mkdirSync("e2e-results", { recursive: true });
  writeFileSync(BEFORE_FILE, JSON.stringify(sessions.map((s) => s.id)));
}
