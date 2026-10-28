import { useEffect, useRef } from "react";

import ChatInput from "./ChatInput.jsx";
import styles from "./ChatWindow.module.css";
import MessageBubble from "./MessageBubble.jsx";

const EXAMPLES = [
  "What does error E-207 mean?",
  "How long is the warranty, and how do I make a claim?",
  "How do I make a signed token expire with itsdangerous?",
];

/** The open conversation: its turns, an empty state with example questions, and the input. */
export default function ChatWindow({ title, turns, busy, loading, onSend, onStop }) {
  const endRef = useRef(null);
  const last = turns.at(-1);

  // Keep the newest text in view while it streams in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns.length, last?.answer, last?.steps.length, last?.status]);

  return (
    <div className={styles.window}>
      <header className={styles.header}>
        <h1 className={styles.title}>{title}</h1>
      </header>

      <div className={styles.scroll}>
        <div className={styles.content}>
          {loading && <p className={styles.loading}>Loading conversation…</p>}

          {!loading && turns.length === 0 && (
            <div className={styles.empty}>
              <h2>Ask your documents</h2>
              <p>
                Answers come only from your indexed files and repositories, with numbered citations
                you can click to check.
              </p>
              <div className={styles.examples}>
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    className={styles.example}
                    disabled={busy}
                    onClick={() => onSend(example)}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <MessageBubble key={turn.id} turn={turn} />
          ))}
          <div ref={endRef} />
        </div>
      </div>

      <div className={styles.footer}>
        <ChatInput onSend={onSend} onStop={onStop} busy={busy} disabled={loading} />
        <p className={styles.hint}>Enter to send · Shift+Enter for a new line</p>
      </div>
    </div>
  );
}
