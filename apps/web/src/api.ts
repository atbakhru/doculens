export const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(
  /\/$/,
  "",
);
export const asset = (url: string) => (url.startsWith("/") ? BASE + url : url);
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = sessionStorage.getItem("doculens-token");
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${res.status})`,
    );
  }
  return res.json();
}
export const post = <T>(path: string, body = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export type Page = {
  id: string;
  document_id: string;
  filename: string;
  page_no: number;
  thumbnail_url: string;
  image_url: string;
  model_version: string;
  width: number;
  height: number;
  sha256: string;
  phash: string;
  duration_ms: number;
  similarity?: number;
};
export type Doc = {
  id: string;
  filename: string;
  status: string;
  page_count: number;
  processed_pages: number;
  error: string | null;
  attempts: number;
};
export type Batch = { id: string; name: string };
export type Run = {
  id: string;
  members: Record<string, number>;
  names: Record<string, string>;
  eps: number;
  min_samples: number;
  cluster_count: number;
  noise_count: number;
  model_version: string;
  created_at: number;
};
export type Pair = {
  id: string;
  kind: string;
  left: Page;
  right: Page;
  inlier_ratio: number;
  inliers: number;
  matches: number;
  hash_distance: number;
};
export type Metrics = {
  pages: number;
  complete: number;
  failed: number;
  queued: number;
  documents: number;
  model: string;
  storage: string;
  queue: string;
};
