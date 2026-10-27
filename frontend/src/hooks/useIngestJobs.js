import { useCallback, useEffect, useRef, useState } from "react";

import { getJob, ingestGithub, listDocuments, listJobs, uploadFiles } from "../api/client.js";

const POLL_INTERVAL_MS = 1500;
const isActive = (job) => job.status === "queued" || job.status === "running";
const loadAll = () => Promise.all([listJobs(), listDocuments()]);

/**
 * Ingestion jobs (uploads, GitHub repos) and the indexed documents.
 * While any job is queued or running, its status is polled every 1.5 s.
 * @returns {{jobs: Array<object>, documents: Array<object>, error: string|null,
 *   submitting: boolean, upload: (files: File[]) => Promise<boolean>,
 *   addRepo: (url: string) => Promise<boolean>, refresh: () => Promise<void>}}
 */
export function useIngestJobs() {
  const [jobs, setJobs] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const jobsRef = useRef(jobs);
  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  const apply = useCallback(([jobList, docList]) => {
    setJobs(jobList);
    setDocuments(docList);
    setError(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      apply(await loadAll());
    } catch (err) {
      setError(err.message);
    }
  }, [apply]);

  // Initial load. State is set in the promise callback, and ignored after unmount.
  useEffect(() => {
    let cancelled = false;
    loadAll()
      .then((lists) => !cancelled && apply(lists))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [apply]);

  const hasActive = jobs.some(isActive);
  useEffect(() => {
    if (!hasActive) return undefined;
    const timer = setInterval(async () => {
      const active = jobsRef.current.filter(isActive);
      try {
        const updates = await Promise.all(active.map((job) => getJob(job.id)));
        const byId = new Map(updates.map((job) => [job.id, job]));
        setJobs((list) => list.map((job) => byId.get(job.id) ?? job));
        if (updates.some((job) => !isActive(job))) setDocuments(await listDocuments());
      } catch (err) {
        setError(err.message);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [hasActive]);

  /** Run a submit call, adding the returned job to the top of the list. */
  const submit = useCallback(async (call) => {
    setSubmitting(true);
    try {
      const job = await call();
      setJobs((list) => [job, ...list]);
      setError(null);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setSubmitting(false);
    }
  }, []);

  const upload = useCallback((files) => submit(() => uploadFiles(files)), [submit]);
  const addRepo = useCallback((url) => submit(() => ingestGithub(url.trim())), [submit]);

  return { jobs, documents, error, submitting, upload, addRepo, refresh };
}
