import { describe, expect, it } from "vitest";

import { createSseParser } from "./sse.js";

function collect(chunks, { end = true } = {}) {
  const events = [];
  const parser = createSseParser((event) => events.push(event));
  for (const chunk of chunks) parser.push(chunk);
  if (end) parser.end();
  return events;
}

describe("createSseParser", () => {
  it("parses a complete event with JSON data", () => {
    expect(collect(['event: token\ndata: {"text": "Hi"}\n\n'])).toEqual([
      { event: "token", data: { text: "Hi" } },
    ]);
  });

  it("handles events split across network chunks at any position", () => {
    const stream =
      'event: status\r\ndata: {"step": "Searching"}\r\n\r\nevent: token\r\ndata: {"text": "a"}\r\n\r\n';
    const expected = [
      { event: "status", data: { step: "Searching" } },
      { event: "token", data: { text: "a" } },
    ];
    for (let cut = 1; cut < stream.length; cut += 1) {
      expect(collect([stream.slice(0, cut), stream.slice(cut)])).toEqual(expected);
    }
  });

  it("does not split an event when \\r\\n is cut between two chunks", () => {
    expect(collect(["event: token\r", '\ndata: {"text": "x"}\r', "\n\r\n"])).toEqual([
      { event: "token", data: { text: "x" } },
    ]);
  });

  it("ignores comments (keep-alive pings) and joins multi-line data", () => {
    expect(collect([": ping\n\nevent: note\ndata: line one\ndata: line two\n\n"])).toEqual([
      { event: "note", data: "line one\nline two" },
    ]);
  });

  it("defaults the event name to 'message' and resets it after each event", () => {
    expect(collect(["event: done\ndata: 1\n\ndata: 2\n\n"])).toEqual([
      { event: "done", data: 1 },
      { event: "message", data: 2 },
    ]);
  });

  it("flushes a last event without a trailing blank line on end()", () => {
    expect(collect(["event: done\ndata: {}"])).toEqual([{ event: "done", data: {} }]);
    expect(collect(["event: done\ndata: {}"], { end: false })).toEqual([]);
  });
});
