import { useRef, useState } from "react";

import { useIngestJobs } from "../hooks/useIngestJobs.js";
import { timeAgo } from "../lib/citations.js";
import styles from "./IngestPanel.module.css";

const ACCEPTED = [".pdf", ".md", ".txt", ".docx"];
const MAX_MB = 25; // mirrors MAX_UPLOAD_MB; the server enforces the real limit

/** Add knowledge (file uploads, GitHub repos), follow ingestion jobs, list indexed documents. */
export default function IngestPanel() {
  const { jobs, documents, error, submitting, upload, addRepo } = useIngestJobs();
  const [repoUrl, setRepoUrl] = useState("");
  const [localError, setLocalError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef(null);

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList);
    const bad = files.find(
      (f) => !ACCEPTED.some((ext) => f.name.toLowerCase().endsWith(ext)) || f.size > MAX_MB * 1e6,
    );
    if (bad) {
      setLocalError(`${bad.name}: use ${ACCEPTED.join(", ")} files up to ${MAX_MB} MB.`);
      return;
    }
    setLocalError(null);
    if (files.length > 0) await upload(files);
    if (fileInput.current) fileInput.current.value = "";
  };

  const submitRepo = async (event) => {
    event.preventDefault();
    setLocalError(null); // show this action's result, not an older message
    if (await addRepo(repoUrl)) setRepoUrl("");
  };

  const shownError = localError ?? error;
  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h1>Knowledge base</h1>
        <p>Everything the assistant can answer from. New content is searchable within seconds.</p>
      </header>

      <div className={styles.content}>
        {shownError && (
          <p className={styles.error} role="alert">
            {shownError}
          </p>
        )}

        <div className={styles.addRow}>
          <section
            className={styles.card}
            data-dragging={dragging}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              handleFiles(event.dataTransfer.files);
            }}
          >
            <h2>Upload documents</h2>
            <p>Drop PDF, Markdown, text or Word files here, or choose them.</p>
            <label className={styles.button}>
              Choose files
              <input
                ref={fileInput}
                type="file"
                multiple
                accept={ACCEPTED.join(",")}
                className="sr-only"
                disabled={submitting}
                onChange={(event) => handleFiles(event.target.files)}
              />
            </label>
          </section>

          <section className={styles.card}>
            <h2>Add a GitHub repository</h2>
            <p>Public repositories only. Code and docs are indexed; nothing is executed.</p>
            <form className={styles.repoForm} onSubmit={submitRepo}>
              <label htmlFor="repo-url" className="sr-only">
                GitHub repository URL
              </label>
              <input
                id="repo-url"
                type="url"
                required
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
              />
              <button type="submit" className={styles.button} disabled={submitting || !repoUrl}>
                Add
              </button>
            </form>
          </section>
        </div>

        <section>
          <h2 className={styles.sectionTitle}>Recent jobs</h2>
          {jobs.length === 0 ? (
            <p className={styles.muted}>No ingestion jobs yet.</p>
          ) : (
            <ul className={styles.jobs}>
              {jobs.map((job) => (
                <JobRow key={job.id} job={job} />
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className={styles.sectionTitle}>
            Indexed documents <span className={styles.count}>{documents.length}</span>
          </h2>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Source</th>
                  <th scope="col">Type</th>
                  <th scope="col">Chunks</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td className={styles.source} title={doc.source}>
                      {doc.source}
                    </td>
                    <td>{doc.file_type}</td>
                    <td>{doc.chunk_count}</td>
                    <td>{timeAgo(doc.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

const STATUS_LABEL = { queued: "Queued", running: "Running", succeeded: "Done", failed: "Failed" };

/** One ingestion job with a progress bar and its outcome summary. */
function JobRow({ job }) {
  const percent =
    job.progress_total > 0 ? Math.round((job.progress_done / job.progress_total) * 100) : 0;
  const summary = Object.entries(job.summary)
    .map(([outcome, count]) => `${count} ${outcome}`)
    .join(", ");
  const failures = job.results.filter((r) => r.outcome === "failed");
  return (
    <li className={styles.job}>
      <div className={styles.jobTop}>
        <span className={styles.status} data-status={job.status}>
          {STATUS_LABEL[job.status] ?? job.status}
        </span>
        <span className={styles.target} title={job.target}>
          {job.kind === "github" ? "GitHub · " : "Upload · "}
          {job.target}
        </span>
        <span className={styles.muted}>{timeAgo(job.created_at)}</span>
      </div>
      {job.status === "running" && (
        <div
          className={styles.progress}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Ingesting ${job.target}`}
        >
          <span style={{ width: `${percent}%` }} />
        </div>
      )}
      {job.status === "running" && job.progress_total > 0 && (
        <p className={styles.muted}>
          {job.progress_done} of {job.progress_total} files
        </p>
      )}
      {summary && <p className={styles.summary}>{summary}</p>}
      {job.error && <p className={styles.jobError}>{job.error}</p>}
      {failures.length > 0 && (
        <details className={styles.failures}>
          <summary>{failures.length} file(s) could not be indexed</summary>
          <ul>
            {failures.map((f) => (
              <li key={f.file}>
                <strong>{f.file}</strong>: {f.detail}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}
