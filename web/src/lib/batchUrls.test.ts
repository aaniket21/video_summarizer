import { describe, expect, it } from "vitest";
import { parseBatchUrls } from "./batchUrls";

describe("parseBatchUrls", () => {
  it("splits lines and trims whitespace", () => {
    const input = " https://a.test\n\nhttps://b.test  ";
    expect(parseBatchUrls(input)).toEqual(["https://a.test", "https://b.test"]);
  });

  it("removes duplicates", () => {
    const input = "https://a.test\nhttps://a.test\nhttps://b.test";
    expect(parseBatchUrls(input)).toEqual(["https://a.test", "https://b.test"]);
  });
});
