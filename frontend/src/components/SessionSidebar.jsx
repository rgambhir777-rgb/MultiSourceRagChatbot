import { timeAgo } from "../lib/citations.js";
import styles from "./SessionSidebar.module.css";

/** Conversation list, "New chat", and the switch between the Chat and Knowledge base views. */
export default function SessionSidebar({
  sessions,
  activeId,
  view,
  error,
  open,
  onSelect,
  onNew,
  onDelete,
  onViewChange,
}) {
  return (
    <aside className={styles.sidebar} data-open={open} aria-label="Conversations">
      <div className={styles.brand}>
        <span className={styles.logo} aria-hidden="true" />
        <span>MultiSource RAG</span>
      </div>

      <nav className={styles.tabs} aria-label="Views">
        {[
          ["chat", "Chat"],
          ["knowledge", "Knowledge base"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={styles.tab}
            aria-current={view === key ? "page" : undefined}
            onClick={() => onViewChange(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      <button type="button" className={styles.newChat} onClick={onNew}>
        + New chat
      </button>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <ul className={styles.list}>
        {sessions.map((session) => (
          <li key={session.id} className={styles.row} data-active={session.id === activeId}>
            <button type="button" className={styles.session} onClick={() => onSelect(session.id)}>
              <span className={styles.sessionTitle}>{session.title}</span>
              <span className={styles.sessionMeta}>
                {session.turn_count} {session.turn_count === 1 ? "message" : "messages"} ·{" "}
                {timeAgo(session.updated_at)}
              </span>
            </button>
            <button
              type="button"
              className={styles.delete}
              aria-label={`Delete conversation: ${session.title}`}
              title="Delete conversation"
              onClick={() => {
                if (window.confirm("Delete this conversation? This cannot be undone.")) {
                  onDelete(session.id);
                }
              }}
            >
              ×
            </button>
          </li>
        ))}
        {sessions.length === 0 && !error && (
          <li className={styles.emptyList}>No conversations yet.</li>
        )}
      </ul>
    </aside>
  );
}
