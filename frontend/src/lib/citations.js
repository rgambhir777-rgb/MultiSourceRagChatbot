// Turn "[1]" citation markers in an answer into clickable links (#cite-1), so the UI can
// open the matching source. Code is left untouched: in code, x[1] is an array index.

const CODE_SPANS = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;
// "[12]" not preceded by a word character (so items[1] stays as it is) and not already a link.
const CITATION = /(?<!\w)\[(\d{1,2})\](?!\()/g;

/**
 * Replace citation markers outside code with Markdown links to "#cite-N".
 * @param {string} markdown
 * @returns {string}
 */
export function linkCitations(markdown) {
  return markdown
    .split(CODE_SPANS)
    .map((part, index) => (index % 2 === 1 ? part : part.replace(CITATION, "[[$1]](#cite-$1)")))
    .join("");
}

/**
 * Format a timestamp as a short relative time ("just now", "5 min ago", "3 d ago").
 * @param {string} iso - ISO date string from the API
 * @param {number} [now] - current time in ms (for tests)
 */
export function timeAgo(iso, now = Date.now()) {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}
