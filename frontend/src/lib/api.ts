/* api.ts — Typed API client for the Ironsite FastAPI backend */

export interface StatusResponse {
  status: "uploaded" | "processing" | "complete" | "error";
  step: string;
  error: string | null;
}

export interface ReportResponse {
  markdown: string;
}

export interface SidecarEvent {
  event_id: string;
  event_type: string;
  severity: string;
  video_file: string;
  timestamp_sec: number;
  timestamp_fmt: string;
  confidence: number;
  clip_path?: string;
  [key: string]: unknown;
}

export interface SidecarMetrics {
  safety: { score: number };
  ergonomics: { score: number };
  productivity: { score: number };
  quality: { score: number };
}

export interface SidecarResponse {
  run_mode: string;
  run_timestamp: string;
  videos: { filename: string; duration_sec: number }[];
  event_count: number;
  keyframe_count: number;
  metrics: SidecarMetrics;
  events: SidecarEvent[];
  [key: string]: unknown;
}

export interface RunInfo {
  run_id: string;
  status: string;
  step: string;
}

export async function uploadVideos(files: File[]): Promise<string> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  const data = await res.json();
  return data.run_id as string;
}

export async function startAnalysis(runId: string): Promise<void> {
  const res = await fetch(`/api/analyze/${runId}`, { method: "POST" });
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`);
}

export async function getStatus(runId: string): Promise<StatusResponse> {
  const res = await fetch(`/api/status/${runId}`);
  if (!res.ok) throw new Error(`Status failed: ${res.status}`);
  return res.json();
}

export async function getReport(runId: string): Promise<string> {
  const res = await fetch(`/api/report/${runId}`);
  if (!res.ok) throw new Error(`Report failed: ${res.status}`);
  const data: ReportResponse = await res.json();
  return data.markdown;
}

export async function getSidecar(runId: string): Promise<SidecarResponse> {
  const res = await fetch(`/api/sidecar/${runId}`);
  if (!res.ok) throw new Error(`Sidecar failed: ${res.status}`);
  return res.json();
}

export function getClipUrl(runId: string, clipPath: string): string {
  return `/api/clips/${runId}/${clipPath}`;
}

export async function listRuns(): Promise<RunInfo[]> {
  const res = await fetch("/api/runs");
  if (!res.ok) throw new Error(`List runs failed: ${res.status}`);
  return res.json();
}

export async function getLatestRun(): Promise<RunInfo> {
  const res = await fetch("/api/runs/latest");
  if (!res.ok) throw new Error(`Latest run failed: ${res.status}`);
  return res.json();
}
