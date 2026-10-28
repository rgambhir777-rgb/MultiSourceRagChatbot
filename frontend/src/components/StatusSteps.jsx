import styles from "./StatusSteps.module.css";

/**
 * The agent's progress while it works ("Searching your documents", "2 passages are relevant").
 * The latest step gets a spinner while the turn is still running.
 */
export default function StatusSteps({ steps, active }) {
  if (steps.length === 0) {
    return active ? <p className={styles.waiting}>Thinking…</p> : null;
  }
  return (
    <ol className={styles.steps} aria-label="Progress">
      {steps.map((step, index) => {
        const current = active && index === steps.length - 1;
        return (
          <li key={`${index}-${step}`} className={current ? styles.current : styles.done}>
            <span className={current ? styles.spinner : styles.check} aria-hidden="true" />
            {step}
          </li>
        );
      })}
    </ol>
  );
}
