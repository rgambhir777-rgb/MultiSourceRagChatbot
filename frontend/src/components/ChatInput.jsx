import { useEffect, useRef, useState } from "react";

import styles from "./ChatInput.module.css";

const MAX_LENGTH = 4000; // matches the API's limit

/**
 * The message box. Enter sends, Shift+Enter adds a new line.
 * While an answer is streaming, the Send button becomes Stop.
 */
export default function ChatInput({ onSend, onStop, busy, disabled }) {
  const [text, setText] = useState("");
  const textarea = useRef(null);

  // Grow with the text, up to a limit.
  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const canSend = !busy && !disabled && text.trim().length > 0;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor="chat-input" className="sr-only">
        Ask a question about your documents
      </label>
      <textarea
        id="chat-input"
        ref={textarea}
        className={styles.input}
        rows={1}
        maxLength={MAX_LENGTH}
        placeholder="Ask about your documents…"
        value={text}
        disabled={disabled}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            submit();
          }
        }}
      />
      {busy ? (
        <button type="button" className={`${styles.button} ${styles.stop}`} onClick={onStop}>
          Stop
        </button>
      ) : (
        <button type="submit" className={styles.button} disabled={!canSend}>
          Send
        </button>
      )}
    </form>
  );
}
