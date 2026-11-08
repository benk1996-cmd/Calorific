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

/** Friendlier wording for Supabase sign-in errors. */
export function loginError(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("rate limit")) return "Too many sign-in emails were requested. Please wait a while, then try once more.";
  if (m.includes("signups not allowed") || m.includes("not allowed for otp"))
    return "This email hasn't been invited yet. Ask the app owner to invite you.";
  if (m.includes("invalid") && m.includes("email")) return "That doesn't look like a valid email address.";
  if (m.includes("failed to fetch") || m.includes("network")) return NETWORK_ERROR;
  return message || "Couldn't send the link. Please try again.";
}
