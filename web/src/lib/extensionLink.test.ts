import { describe, expect, it } from "vitest";
import { getExtensionPayload } from "./extensionLink";

describe("getExtensionPayload", () => {
  it("returns decoded url and source", () => {
    const payload = getExtensionPayload(
      "http://localhost:3000/?url=https%3A%2F%2Fexample.com%2Fvideo.mp4&source=extension"
    );
    expect(payload).toEqual({
      url: "https://example.com/video.mp4",
      source: "extension",
    });
  });

  it("returns null when url is missing", () => {
    const payload = getExtensionPayload("http://localhost:3000/?source=extension");
    expect(payload).toEqual({ url: null, source: "extension" });
  });

  it("rejects non-http urls", () => {
    const payload = getExtensionPayload(
      "http://localhost:3000/?url=javascript%3Aalert(1)&source=extension"
    );
    expect(payload).toEqual({ url: null, source: "extension" });
  });
});
