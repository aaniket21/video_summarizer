const test = require("node:test");
const assert = require("node:assert/strict");

const { parseBatchUrls } = require("./batchUrls");

test("parseBatchUrls splits and trims", () => {
  const input = "https://a.test\n\n https://b.test ";
  assert.deepEqual(parseBatchUrls(input), ["https://a.test", "https://b.test"]);
});
