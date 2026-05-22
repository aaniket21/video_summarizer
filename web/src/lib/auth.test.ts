import { describe, expect, it } from "vitest";

import { buildAuthHeaders } from "./auth";

describe("buildAuthHeaders", () => {
  it("adds authorization header when token is provided", () => {
    const headers = buildAuthHeaders("token-123", {
      "Content-Type": "application/json",
    });

    expect(headers.get("Authorization")).toBe("Bearer token-123");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("does not add authorization when token is missing", () => {
    const headers = buildAuthHeaders("", { Accept: "application/json" });

    expect(headers.get("Authorization")).toBeNull();
    expect(headers.get("Accept")).toBe("application/json");
  });
});
