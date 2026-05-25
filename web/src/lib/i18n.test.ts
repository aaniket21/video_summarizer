import { describe, expect, it } from "vitest";

import { t } from "./i18n";

describe("i18n", () => {
  it("returns a localized string", () => {
    expect(t("inputTitle", "hi")).toBe("इनपुट");
  });

  it("falls back to English when missing", () => {
    expect(t("progressTitle", "xx" as unknown as "en")).toBe("Progress");
  });
});
