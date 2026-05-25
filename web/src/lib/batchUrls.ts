export function parseBatchUrls(input: string) {
  const seen = new Set<string>();
  const result: string[] = [];

  String(input || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((url) => {
      if (!seen.has(url)) {
        seen.add(url);
        result.push(url);
      }
    });

  return result;
}
