// All JSON calls to the backend. Components never call fetch directly: they use hooks,
// and hooks use these functions.

/** Base path of the backend. Relative on purpose: the Vite dev proxy (dev) or nginx (prod)
 * forwards it, so no hostnames or ports are hard-coded in the frontend. */
export const API_BASE = "/api";
const DEFAULT_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 120_000;

/** An error with a message that is safe and useful to show to the user. */
export class ApiError extends Error {
  /**
   * @param {string} message - human-readable explanation
   * @param {number} status - HTTP status (0 = the server could not be reached)
   */
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Turn a failed response into a readable message (FastAPI puts it in `detail`).
 * @param {Response} response
 * @returns {Promise<string>}
 */
export async function errorMessage(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((item) => item.msg).join("; ");
  } catch {
    // not JSON: fall through to the generic message
  }
  return `Request failed (HTTP ${response.status})`;
}

/**
 * Call the API and return parsed JSON (or null for 204 No Content).
 * @param {string} path - path below /api, e.g. "/sessions"
 * @param {{method?: string, json?: unknown, body?: BodyInit, timeoutMs?: number}} [options]
 */
async function request(path, { method = "GET", json, body, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const init = { method, signal: AbortSignal.timeout(timeoutMs) };
  if (json !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(json);
  } else if (body !== undefined) {
    init.body = body;
  }
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    const message =
      error?.name === "TimeoutError"
        ? "The server took too long to respond."
        : "Cannot reach the server. Is the API running?";
    throw new ApiError(message, 0);
  }
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  return response.status === 204 ? null : response.json();
}

/** @returns {Promise<Array<{id: string, title: string, turn_count: number, updated_at: string}>>} */
export const listSessions = () => request("/sessions");

/** Create a new, empty conversation. */
export const createSession = () => request("/sessions", { method: "POST" });

/** Delete a conversation and its memory. @param {string} id */
export const deleteSession = (id) =>
  request(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });

/** Questions, answers and sources of one conversation. @param {string} id */
export const getHistory = (id) => request(`/sessions/${encodeURIComponent(id)}/history`);

/** Every indexed document. */
export const listDocuments = () => request("/documents");

/** Most recent ingestion jobs. @param {number} [limit] */
export const listJobs = (limit = 20) => request(`/jobs?limit=${limit}`);

/** One ingestion job (poll this to follow progress). @param {string} id */
export const getJob = (id) => request(`/jobs/${encodeURIComponent(id)}`);

/**
 * Upload files to be indexed; returns the queued job.
 * @param {File[]} files
 */
export function uploadFiles(files) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return request("/ingest/files", { method: "POST", body: form, timeoutMs: UPLOAD_TIMEOUT_MS });
}

/** Queue indexing of a public GitHub repository. @param {string} url */
export const ingestGithub = (url) => request("/ingest/github", { method: "POST", json: { url } });
