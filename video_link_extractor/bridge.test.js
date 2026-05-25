const test = require("node:test");
const assert = require("node:assert/strict");

const { sanitizeBaseUrl, buildWebAppJobUrl } = require("./bridge");

test("sanitizeBaseUrl trims trailing slashes", () => {
  assert.equal(sanitizeBaseUrl("http://localhost:3000/"), "http://localhost:3000");
  assert.equal(sanitizeBaseUrl("https://lecturelens.ai///"), "https://lecturelens.ai");
});

test("sanitizeBaseUrl adds https for bare host", () => {
  assert.equal(sanitizeBaseUrl("lecturelens.ai"), "https://lecturelens.ai");
});

test("buildWebAppJobUrl encodes url and source", () => {
  const result = buildWebAppJobUrl(
    "http://localhost:3000",
    "https://youtube.com/watch?v=abc&list=1"
  );
  assert.equal(
    result,
    "http://localhost:3000/?url=https%3A%2F%2Fyoutube.com%2Fwatch%3Fv%3Dabc%26list%3D1&source=extension"
  );
});
