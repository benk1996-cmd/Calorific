import { describe, expect, it } from "vitest";
import { friendlyError, NETWORK_ERROR } from "./errors";

describe("friendlyError", () => {
  it("explains expired sessions", () => expect(friendlyError(401, "Invalid or expired session")).toMatch(/sign in again/));
  it("passes through the API's own message for client errors", () => {
    expect(friendlyError(429, "Daily AI limit reached. Use search to add food manually.")).toBe("Daily AI limit reached. Use search to add food manually.");
    expect(friendlyError(415, "Please upload a JPEG, PNG or WebP image")).toMatch(/JPEG/);
  });
  it("keeps the API's busy message for 503, with a fallback", () => {
    expect(friendlyError(503, "The AI service is busy right now. Please try again in a minute.")).toMatch(/AI service is busy/);
    expect(friendlyError(503)).toMatch(/busy/);
    expect(friendlyError(502, "A data service is unavailable.")).toMatch(/unavailable/);
  });
  it("handles gateway timeouts and generic server errors without leaking HTML", () => {
    expect(friendlyError(504, "<html>Gateway Timeout</html>")).toMatch(/too long/);
    expect(friendlyError(500, "Something went wrong. Please try again.")).toMatch(/Something went wrong/);
    expect(friendlyError(500)).toMatch(/our side/);
  });
  it("falls back to status text", () => {
    expect(friendlyError(404, null, "Not Found")).toBe("Not Found");
    expect(friendlyError(418)).toBe("Request failed (418)");
    expect(friendlyError(413)).toMatch(/too large/);
    expect(NETWORK_ERROR).toMatch(/connection/);
  });
});
