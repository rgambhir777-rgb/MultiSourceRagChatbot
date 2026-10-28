import { useCallback, useEffect, useReducer, useRef } from "react";

import { getHistory } from "../api/client.js";
import { streamChat } from "../api/sse.js";

// If the server sends nothing at all for this long (it pings every 15 s while working),
// give up so the UI never hangs silently.
const IDLE_TIMEOUT_MS = 90_000;

let nextTurnId = 1;

/**
 * State of one conversation: a list of turns (question + answer). The last turn is the one
 * being streamed. A reducer keeps every update in one place and easy to test.
 */
function reducer(state, action) {
  // Stream events only ever change the turn that is still streaming (late events from a
  // stream of another conversation, or after a stop, are ignored).
  const updateLast = (change) => {
    const last = state.turns.at(-1);
    if (!last || last.status !== "streaming") return state;
    return { ...state, turns: [...state.turns.slice(0, -1), { ...last, ...change(last) }] };
  };
  switch (action.type) {
    case "loaded":
      return { turns: action.turns, loading: false, busy: false };
    case "loading":
      return { turns: [], loading: true, busy: false };
    case "start":
      return { ...state, busy: true, turns: [...state.turns, action.turn] };
    case "status":
      return updateLast((t) => ({ steps: [...t.steps, action.step] }));
    case "token":
      return updateLast((t) => ({ answer: t.answer + action.text }));
    case "answer_reset": // the grounding check failed: a corrected answer follows
      return updateLast(() => ({ answer: "" }));
    case "sources":
      return updateLast(() => ({ sources: action.sources }));
    case "done":
      return {
        ...updateLast(() => ({
          answer: action.data.answer,
          grounded: action.data.grounded,
          route: action.data.route,
          costUsd: action.data.cost_usd,
          latencyMs: action.data.latency_ms,
          status: "done",
        })),
        busy: false,
      };
    case "error":
      return { ...updateLast(() => ({ status: "error", error: action.message })), busy: false };
    case "stopped":
      return { ...updateLast(() => ({ status: "stopped" })), busy: false };
    default:
      return state;
  }
}

/** Convert a saved turn from the history API into the UI's turn shape. */
function fromHistory(turn) {
  return {
    id: nextTurnId++,
    question: turn.question,
    answer: turn.answer,
    sources: turn.sources,
    grounded: turn.grounded,
    route: turn.route,
    steps: [],
    status: "done",
    error: null,
  };
}

/**
 * Load and stream one conversation.
 * @param {string|null} sessionId - the open conversation
 * @param {{onTurnDone?: () => void}} [options] - e.g. refresh the sidebar titles
 * @returns {{turns: Array<object>, busy: boolean, loading: boolean,
 *   send: (message: string, sessionId?: string) => Promise<void>, stop: () => void}}
 */
export function useChatStream(sessionId, { onTurnDone } = {}) {
  const [state, dispatch] = useReducer(reducer, { turns: [], loading: false, busy: false });
  const controller = useRef(null); // {abort: AbortController, sessionId: string} while streaming
  const version = useRef(0); // bumps when a turn starts, so a late history load can't wipe it
  // Which conversation the turns on screen belong to. A message sent to a brand-new chat
  // claims it before React has even switched to that chat, so the switch must not reload it.
  const shownSession = useRef(undefined);
  const onTurnDoneRef = useRef(onTurnDone);
  useEffect(() => {
    onTurnDoneRef.current = onTurnDone;
  }, [onTurnDone]);

  // Load the conversation when another one is opened; cancel any stream of the old one.
  useEffect(() => {
    if (shownSession.current === sessionId) return undefined; // already on screen
    shownSession.current = sessionId;
    controller.current?.abort.abort();
    if (!sessionId) {
      dispatch({ type: "loaded", turns: [] });
      return undefined;
    }
    const loadVersion = ++version.current;
    let cancelled = false;
    let settled = false;
    dispatch({ type: "loading" });
    getHistory(sessionId)
      .then((history) => {
        if (!cancelled && version.current === loadVersion) {
          dispatch({ type: "loaded", turns: history.turns.map(fromHistory) });
        }
      })
      .catch(() => {
        if (!cancelled && version.current === loadVersion) dispatch({ type: "loaded", turns: [] });
      })
      .finally(() => {
        settled = true;
      });
    return () => {
      cancelled = true;
      // Cancelled before the history arrived (e.g. React's development double-run of effects):
      // forget the claim, so the next run loads it again instead of waiting forever.
      if (!settled && shownSession.current === sessionId) shownSession.current = undefined;
    };
  }, [sessionId]);

  // Abort a running stream when the component goes away.
  useEffect(() => () => controller.current?.abort.abort(), []);

  const send = useCallback(
    async (message, targetSession = sessionId) => {
      const text = message.trim();
      if (!text || !targetSession || controller.current) return;
      version.current += 1;
      const abort = new AbortController();
      controller.current = { abort, sessionId: targetSession };
      shownSession.current = targetSession;
      dispatch({
        type: "start",
        turn: {
          id: nextTurnId++,
          question: text,
          answer: "",
          sources: [],
          grounded: null,
          route: null,
          steps: [],
          status: "streaming",
          error: null,
        },
      });

      let idleTimer;
      let timedOut = false;
      const resetIdle = () => {
        clearTimeout(idleTimer);
        idleTimer = setTimeout(() => {
          timedOut = true;
          abort.abort();
        }, IDLE_TIMEOUT_MS);
      };
      let finished = false;
      resetIdle();
      try {
        await streamChat({
          sessionId: targetSession,
          message: text,
          signal: abort.signal,
          onEvent: ({ event, data }) => {
            resetIdle();
            if (event === "status") dispatch({ type: "status", step: data.step });
            else if (event === "token") dispatch({ type: "token", text: data.text });
            else if (event === "answer_reset") dispatch({ type: "answer_reset" });
            else if (event === "sources") dispatch({ type: "sources", sources: data.sources });
            else if (event === "done") {
              finished = true;
              dispatch({ type: "done", data });
            } else if (event === "error") {
              finished = true;
              dispatch({ type: "error", message: data.message });
            }
          },
        });
        if (!finished) dispatch({ type: "error", message: "The answer stopped unexpectedly." });
        else onTurnDoneRef.current?.();
      } catch (error) {
        if (timedOut) dispatch({ type: "error", message: "The server stopped responding." });
        else if (error?.name === "AbortError") dispatch({ type: "stopped" });
        else dispatch({ type: "error", message: error.message });
      } finally {
        clearTimeout(idleTimer);
        if (controller.current?.abort === abort) controller.current = null;
      }
    },
    [sessionId],
  );

  const stop = useCallback(() => controller.current?.abort.abort(), []);

  return { turns: state.turns, busy: state.busy, loading: state.loading, send, stop };
}
