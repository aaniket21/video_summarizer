const test = require("node:test");
const assert = require("node:assert/strict");

const { normalizeApiBaseUrl, buildJobsUrl } = require("./cloudSync");

test("normalizeApiBaseUrl trims trailing slashes", () => {
  assert.equal(normalizeApiBaseUrl("http://localhost:8000/"), "http://localhost:8000");
  assert.equal(normalizeApiBaseUrl("https://api.example.com///"), "https://api.example.com");
});

test("buildJobsUrl builds list endpoint with paging", () => {
  assert.equal(
    buildJobsUrl("http://localhost:8000", 2, 25),
    "http://localhost:8000/api/v1/jobs?page=2&limit=25"
  );
});
