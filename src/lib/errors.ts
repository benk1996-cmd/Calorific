/** Turn an HTTP failure into a message a person can act on. `detail` is the API's own message, if any. */
export function friendlyError(status: number, detail?: string | null, statusText = ""): string {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (detail && status !== 502 && status !== 503 && status !== 504) return detail;
  if (status === 502 || status === 503) return detail || "The server is busy right now. Please try again in a moment.";
  if (status === 504) return "The request took too long. Please try again.";
  if (status === 413) return "That file is too large.";
  if (status >= 500) return "Something went wrong on our side. Please try again.";
  return statusText || `Request failed (${status})`;
}

export const NETWORK_ERROR = "Can't reach the server. Check your connection and try again.";
