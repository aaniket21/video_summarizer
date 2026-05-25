(function (root) {
  function parseBatchUrls(input) {
    return String(input || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  const api = { parseBatchUrls };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  root.BatchUrls = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
