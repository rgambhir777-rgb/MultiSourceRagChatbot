import { useCallback, useEffect, useRef, useState } from "react";

import { createSession, deleteSession, listSessions } from "../api/client.js";

const STORAGE_KEY = "ragchat.activeSession";

/** Read the last open conversation id (a per-browser convenience; may be unavailable). */
function loadActiveId() {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Remember the open conversation id in this browser (ignored if storage is blocked). */
function saveActiveId(id) {
  try {
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // private mode or blocked storage: the app works without it
  }
}

/**
 * The list of conversations and which one is open.
 * @returns {{sessions: Array<object>, activeId: string|null, error: string|null,
 *   select: (id: string|null) => void, newChat: () => Promise<object>,
 *   remove: (id: string) => Promise<void>, refresh: () => Promise<void>}}
 */
export function useSessions() {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(loadActiveId);
  const [error, setError] = useState(null);
  // The latest activeId, readable inside async callbacks without re-creating them.
  const activeRef = useRef(activeId);
  // Set once the user picks a conversation (or "New chat"): from then on, loading the list
  // must never switch conversations behind their back.
  const userChose = useRef(false);

  const open = useCallback((id) => {
    activeRef.current = id;
    setActiveId(id);
    saveActiveId(id);
  }, []);

  /** Open a conversation because the user asked for it (null = a new, empty chat). */
  const select = useCallback(
    (id) => {
      userChose.current = true;
      open(id);
    },
    [open],
  );

  const applyList = useCallback(
    (list) => {
      setSessions(list);
      setError(null);
      // On first load, open the remembered conversation, or the latest one if it's gone.
      if (!userChose.current && !list.some((s) => s.id === activeRef.current)) {
        open(list[0]?.id ?? null);
      }
    },
    [open],
  );

  const refresh = useCallback(async () => {
    try {
      applyList(await listSessions());
    } catch (err) {
      setError(err.message);
    }
  }, [applyList]);

  const newChat = useCallback(async () => {
    const session = await createSession();
    setSessions((list) => [session, ...list]);
    select(session.id);
    return session;
  }, [select]);

  const remove = useCallback(
    async (id) => {
      try {
        await deleteSession(id);
      } catch (err) {
        setError(err.message);
        return;
      }
      const rest = sessions.filter((s) => s.id !== id);
      setSessions(rest);
      if (activeRef.current === id) select(rest[0]?.id ?? null);
    },
    [sessions, select],
  );

  // Initial load. State is set in the promise callback, and ignored after unmount.
  useEffect(() => {
    let cancelled = false;
    listSessions()
      .then((list) => !cancelled && applyList(list))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [applyList]);

  return { sessions, activeId, error, select, newChat, remove, refresh };
}
