import { describe, expect, it } from "vitest";

import { linkCitations, timeAgo } from "./citations.js";

describe("linkCitations", () => {
  it("links citation markers", () => {
    expect(linkCitations("Use a C-wire [1][2].")).toBe(
      "Use a C-wire [[1]](#cite-1)[[2]](#cite-2).",
    );
  });

  it("leaves code blocks and inline code alone", () => {
    const text = "See [1].\n```python\nvalue = items[1]\n```\nAlso `x[2]` and [3].";
    expect(linkCitations(text)).toBe(
      "See [[1]](#cite-1).\n```python\nvalue = items[1]\n```\nAlso `x[2]` and [[3]](#cite-3).",
    );
  });

  it("does not touch array indexing or existing links", () => {
    expect(linkCitations("items[1] and [docs](http://x) and [4](#y)")).toBe(
      "items[1] and [docs](http://x) and [4](#y)",
    );
  });
});

describe("timeAgo", () => {
  const now = Date.parse("2026-10-27T12:00:00Z");
  it.each([
    ["2026-10-27T11:59:30Z", "just now"],
    ["2026-10-27T11:55:00Z", "5 min ago"],
    ["2026-10-27T09:00:00Z", "3 h ago"],
    ["2026-10-24T12:00:00Z", "3 d ago"],
  ])("%s -> %s", (iso, expected) => {
    expect(timeAgo(iso, now)).toBe(expected);
  });
});
