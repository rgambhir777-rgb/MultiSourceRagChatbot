import { useState } from "react";

import styles from "./App.module.css";
import ChatWindow from "./components/ChatWindow.jsx";
import IngestPanel from "./components/IngestPanel.jsx";
import SessionSidebar from "./components/SessionSidebar.jsx";
import { useChatStream } from "./hooks/useChatStream.js";
import { useSessions } from "./hooks/useSessions.js";

/** App layout: conversations sidebar + the Chat or Knowledge base view. */
export default function App() {
  const [view, setView] = useState("chat");
  const [menuOpen, setMenuOpen] = useState(false);
  const sessions = useSessions();
  const chat = useChatStream(sessions.activeId, { onTurnDone: sessions.refresh });
  const [sendError, setSendError] = useState(null);

  const active = sessions.sessions.find((s) => s.id === sessions.activeId);

  const handleSend = async (text) => {
    setSendError(null);
    let sessionId = sessions.activeId;
    if (!sessionId) {
      try {
        sessionId = (await sessions.newChat()).id; // first message creates the conversation
      } catch (err) {
        setSendError(err.message);
        return;
      }
    }
    await chat.send(text, sessionId);
  };

  const closeMenuThen =
    (fn) =>
    (...args) => {
      setMenuOpen(false);
      return fn(...args);
    };

  return (
    <div className={styles.app}>
      <button
        type="button"
        className={styles.menuButton}
        aria-label="Open conversations"
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((open) => !open)}
      >
        ☰
      </button>
      {menuOpen && (
        <div className={styles.backdrop} onClick={() => setMenuOpen(false)} aria-hidden="true" />
      )}

      <SessionSidebar
        sessions={sessions.sessions}
        activeId={sessions.activeId}
        view={view}
        error={sessions.error}
        open={menuOpen}
        onSelect={closeMenuThen((id) => {
          sessions.select(id);
          setView("chat");
        })}
        onNew={closeMenuThen(() => {
          // The conversation is created on the server when its first message is sent
          // (handleSend), so clicking "New chat" never leaves empty conversations behind.
          setView("chat");
          setSendError(null);
          sessions.select(null);
        })}
        onDelete={sessions.remove}
        onViewChange={closeMenuThen(setView)}
      />

      <main className={styles.main}>
        {view === "knowledge" ? (
          <IngestPanel />
        ) : (
          <>
            {sendError && (
              <p className={styles.banner} role="alert">
                {sendError}
              </p>
            )}
            <ChatWindow
              title={active?.title ?? "New chat"}
              turns={chat.turns}
              busy={chat.busy}
              loading={chat.loading}
              onSend={handleSend}
              onStop={chat.stop}
            />
          </>
        )}
      </main>
    </div>
  );
}
