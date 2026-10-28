// After all E2E tests: delete the conversations the tests created, so the sidebar only shows
// your own chats. (The uploaded test document stays indexed; later runs simply skip it.)
import { readFileSync } from "node:fs";

import { API, BEFORE_FILE } from "./global-setup.js";

export default async function globalTeardown() {
  const before = new Set(JSON.parse(readFileSync(BEFORE_FILE, "utf8")));
  const now = await (await fetch(`${API}/api/sessions?limit=200`)).json();
  const created = now.filter((session) => !before.has(session.id));
  await Promise.all(
    created.map((session) => fetch(`${API}/api/sessions/${session.id}`, { method: "DELETE" })),
  );
  console.log(`E2E clean-up: deleted ${created.length} test conversation(s).`);
}
