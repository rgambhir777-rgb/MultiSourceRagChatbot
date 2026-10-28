import { useEffect, useRef } from "react";

import styles from "./SourceList.module.css";

/**
 * The passages an answer was based on, numbered like the [n] citations.
 * Clicking a citation opens the list and highlights that source.
 */
export default function SourceList({ sources, open, onToggle, highlighted }) {
  const itemRefs = useRef({});

  useEffect(() => {
    if (open && highlighted) itemRefs.current[highlighted]?.scrollIntoView({ block: "nearest" });
  }, [open, highlighted]);

  if (sources.length === 0) return null;
  const cited = sources.filter((s) => s.cited).length;
  return (
    <section className={styles.sources}>
      <button type="button" className={styles.toggle} onClick={onToggle} aria-expanded={open}>
        <span className={styles.chevron} data-open={open} aria-hidden="true" />
        Sources ({cited} cited{sources.length > cited ? `, ${sources.length - cited} more` : ""})
      </button>
      {open && (
        <ol className={styles.list}>
          {sources.map((source) => (
            <li
              key={source.number}
              ref={(el) => {
                itemRefs.current[source.number] = el;
              }}
              className={[
                styles.item,
                source.cited ? styles.cited : "",
                highlighted === source.number ? styles.highlighted : "",
              ].join(" ")}
            >
              <div className={styles.header}>
                <span className={styles.number}>{source.number}</span>
                <span className={styles.location} title={source.location}>
                  {source.location}
                </span>
              </div>
              <p className={styles.snippet}>{source.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
