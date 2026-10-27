// Streaming chat: POST a message and read the Server-Sent Events (SSE) of the answer.
//
// The browser's built-in EventSource only supports GET requests, so we use fetch() and read
// the response body piece by piece. Network pieces can end anywhere, even in the middle of
// a line, so the parser buffers incomplete lines until the rest arrives.

import { API_BASE, ApiError, errorMessage } from "./client.js";

/**
 * Create an incremental SSE parser.
 * Events are separated by a blank line; each has an `event:` name and `data:` lines.
 * Lines may end with \n, \r\n or \r. Lines starting with ":" are comments (keep-alive pings).
 *
 * @param {(event: {event: string, data: unknown}) => void} onEvent - called per complete event
 * @returns {{push: (text: string) => void, end: () => void}}
 */
export function createSseParser(onEvent) {
  let buffer = "";
  let eventName = "message";
  let dataLines = [];

  function dispatch() {
    if (dataLines.length > 0) {
      const raw = dataLines.join("\n");
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        data = raw;
      }
      onEvent({ event: eventName, data });
    }
    eventName = "message";
    dataLines = [];
  }

  function processLine(line) {
    if (line === "") return dispatch();
    if (line.startsWith(":")) return; // comment / keep-alive
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") eventName = value;
    else if (field === "data") dataLines.push(value);
  }

  return {
    push(text) {
      buffer += text;
      // A chunk ending in "\r" might be the first half of "\r\n": wait for the next chunk,
      // or the "\n" would look like an extra blank line and end the event too early.
      const holdCarriageReturn = buffer.endsWith("\r");
      const usable = holdCarriageReturn ? buffer.slice(0, -1) : buffer;
      const lines = usable.split(/\r\n|\r|\n/);
      buffer = lines.pop() + (holdCarriageReturn ? "\r" : "");
      for (const line of lines) processLine(line);
    },
    end() {
      const rest = buffer.replace(/\r$/, "");
      buffer = "";
      if (rest) processLine(rest);
      dispatch();
    },
  };
}

/**
 * Send a chat message and call `onEvent` for each streamed event
 * (status, token, answer_reset, sources, done, error). Resolves when the stream ends.
 * Abort it with `signal` (e.g. the Stop button).
 *
 * @param {{sessionId: string, message: string, signal?: AbortSignal,
 *          onEvent: (event: {event: string, data: any}) => void}} options
 */
export async function streamChat({ sessionId, message, signal, onEvent }) {
  let response;
  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("Cannot reach the server. Is the API running?", 0);
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);

  const reader = response.body.getReader();
  const decoder = new TextDecoder(); // {stream: true} keeps multi-byte characters intact
  const parser = createSseParser(onEvent);
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.push(decoder.decode());
  parser.end();
}
