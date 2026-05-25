(function (root) {
  function normalizeApiBaseUrl(input) {
    const value = String(input || "").trim();
    if (!value) return "";
    return value.replace(/\/+$/, "");
  }

  function buildJobsUrl(baseUrl, page, limit) {
    const base = normalizeApiBaseUrl(baseUrl);
    if (!base) return "";
    const url = new URL(`${base}/api/v1/jobs`);
    url.searchParams.set("page", String(page || 1));
    url.searchParams.set("limit", String(limit || 20));
    return url.toString();
  }

  const api = { normalizeApiBaseUrl, buildJobsUrl };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  root.CloudSync = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
