import { describe, expect, it } from "vitest";

import { mapJobToCloudHistoryItem } from "@/lib/cloudHistory";

const baseJob = {
  id: "job-1",
  video_url: "https://example.com/video",
  status: "completed",
  created_at: "2026-05-22T10:20:30Z",
  result: {
    transcript: "Transcript",
    summary: "Summary",
    metadata: { title: "Lecture 1" },
  },
};

describe("mapJobToCloudHistoryItem", () => {
  it("prefers metadata title when present", () => {
    const item = mapJobToCloudHistoryItem(baseJob);
    expect(item.title).toBe("Lecture 1");
    expect(item.source).toBe("https://example.com/video");
    expect(item.status).toBe("completed");
  });

  it("falls back to video_url when title missing", () => {
    const item = mapJobToCloudHistoryItem({
      ...baseJob,
      result: { transcript: "", summary: "", metadata: {} },
    });
    expect(item.title).toBe("https://example.com/video");
  });

  it("handles missing result gracefully", () => {
    const item = mapJobToCloudHistoryItem({
      id: "job-2",
      video_url: "https://example.com/video-2",
      status: "processing",
      created_at: "2026-05-22T11:20:30Z",
      result: null,
    });
    expect(item.title).toBe("https://example.com/video-2");
  });
});
