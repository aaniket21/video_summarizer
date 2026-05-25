(function (root) {
  function sanitizeBaseUrl(input) {
    const value = String(input || "").trim();
    if (!value) return "";

    const withScheme = /^https?:\/\//i.test(value) ? value : `https://${value}`;
    return withScheme.replace(/\/+$/, "");
  }

  function buildWebAppJobUrl(baseUrl, videoUrl) {
    const sanitizedBase = sanitizeBaseUrl(baseUrl);
    if (!sanitizedBase) return "";

    let target;
    try {
      target = new URL(sanitizedBase);
    } catch {
      return "";
    }

    if (!target.pathname.endsWith("/")) {
      target.pathname = `${target.pathname}/`;
    }

    target.searchParams.set("url", String(videoUrl || ""));
    target.searchParams.set("source", "extension");
    return target.toString();
  }

  const api = { sanitizeBaseUrl, buildWebAppJobUrl };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  root.LectureLensBridge = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
