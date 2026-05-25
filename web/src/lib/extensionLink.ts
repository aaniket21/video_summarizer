export type ExtensionPayload = {
  url: string | null;
  source: string | null;
};

function isAllowedUrl(value: string) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function getExtensionPayload(href: string): ExtensionPayload {
  try {
    const parsed = new URL(href);
    const source = parsed.searchParams.get("source");
    const rawUrl = parsed.searchParams.get("url") || "";
    if (!rawUrl) {
      return { url: null, source };
    }

    const decodedUrl = rawUrl;
    if (!isAllowedUrl(decodedUrl)) {
      return { url: null, source };
    }

    return { url: decodedUrl, source };
  } catch {
    return { url: null, source: null };
  }
}
