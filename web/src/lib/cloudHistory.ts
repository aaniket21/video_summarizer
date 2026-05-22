import { apiFetch } from "@/lib/api";

export type ApiJobResult = {
  transcript?: string | null;
  summary?: string | null;
  metadata?: { title?: string | null } | null;
} | null;

export type ApiJob = {
  id: string;
  video_url: string;
  status: string;
  created_at: string;
  result?: ApiJobResult;
};

export type CloudHistoryItem = {
  id: string;
  title: string;
  source: string;
  status: string;
  createdAt: number;
};

export function mapJobToCloudHistoryItem(job: ApiJob): CloudHistoryItem {
  const title = job.result?.metadata?.title?.trim() || job.video_url;
  const createdAt = Date.parse(job.created_at);
  return {
    id: job.id,
    title,
    source: job.video_url,
    status: job.status,
    createdAt: Number.isNaN(createdAt) ? Date.now() : createdAt,
  };
}

export async function fetchCloudHistory(accessToken: string, limit = 20): Promise<CloudHistoryItem[]> {
  const res = await apiFetch(`/api/v1/jobs?limit=${limit}`, {}, accessToken);
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    const message = payload?.error || `Cloud history failed (${res.status}).`;
    throw new Error(message);
  }
  const payload = (await res.json()) as { items?: ApiJob[] };
  const items = Array.isArray(payload.items) ? payload.items : [];
  return items.map(mapJobToCloudHistoryItem);
}
