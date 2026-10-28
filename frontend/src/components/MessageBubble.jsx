import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { linkCitations } from "../lib/citations.js";
import GroundingBadge from "./GroundingBadge.jsx";
import styles from "./MessageBubble.module.css";
import SourceList from "./SourceList.jsx";
import StatusSteps from "./StatusSteps.jsx";

/**
 * One turn of the conversation: the user's question and the assistant's answer.
 * The answer is model output, so it is UNTRUSTED: it is rendered with react-markdown (raw HTML
 * is shown as text, never executed), and links open safely in a new tab.
 */
export default function MessageBubble({ turn }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(null);
  const streaming = turn.status === "streaming";

  const showSource = (number) => {
    setSourcesOpen(true);
    setHighlighted(number);
  };

  const markdownComponents = {
    a: ({ href, children }) =>
      href?.startsWith("#cite-") ? (
        <button
          type="button"
          className={styles.cite}
          onClick={() => showSource(Number(href.slice("#cite-".length)))}
          aria-label={`Show source ${href.slice("#cite-".length)}`}
        >
          {String(children).replace(/[[\]]/g, "")}
        </button>
      ) : (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      ),
  };

  return (
    <article className={styles.turn}>
      <div className={styles.question}>
        <p>{turn.question}</p>
      </div>

      <div className={styles.answer}>
        <div className={styles.avatar} aria-hidden="true">
          AI
        </div>
        <div className={styles.body}>
          {streaming && <StatusSteps steps={turn.steps} active />}

          <div className={styles.markdown} aria-live={streaming ? "polite" : "off"}>
            {turn.answer && (
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {linkCitations(turn.answer)}
              </ReactMarkdown>
            )}
            {streaming && turn.answer && <span className={styles.caret} aria-hidden="true" />}
          </div>

          {turn.status === "error" && (
            <p className={styles.error} role="alert">
              {turn.error}
            </p>
          )}
          {turn.status === "stopped" && <p className={styles.note}>Stopped.</p>}

          {turn.status === "done" && (
            <div className={styles.meta}>
              <GroundingBadge grounded={turn.grounded} route={turn.route} />
              {turn.latencyMs != null && (
                <span className={styles.stats}>
                  {(turn.latencyMs / 1000).toFixed(1)} s
                  {turn.costUsd != null && ` · $${turn.costUsd.toFixed(4)}`}
                </span>
              )}
            </div>
          )}

          <SourceList
            sources={turn.sources}
            open={sourcesOpen}
            onToggle={() => setSourcesOpen((open) => !open)}
            highlighted={highlighted}
          />
        </div>
      </div>
    </article>
  );
}
