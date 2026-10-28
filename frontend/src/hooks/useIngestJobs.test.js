import { describe, expect, it } from "vitest";

import { mergeJobs } from "./useIngestJobs.js";

describe("mergeJobs", () => {
  it("keeps a just-uploaded job that an older server list doesn't contain yet", () => {
    const shown = [
      { id: "new", status: "queued" },
      { id: "a", status: "running" },
    ];
    const fromServer = [
      { id: "a", status: "succeeded" },
      { id: "b", status: "failed" },
    ];
    expect(mergeJobs(fromServer, shown)).toEqual([
      { id: "new", status: "queued" },
      { id: "a", status: "succeeded" },
      { id: "b", status: "failed" },
    ]);
  });

  it("uses the server's version of jobs it already knows", () => {
    const merged = mergeJobs([{ id: "a", status: "succeeded" }], [{ id: "a", status: "queued" }]);
    expect(merged).toEqual([{ id: "a", status: "succeeded" }]);
  });
});
