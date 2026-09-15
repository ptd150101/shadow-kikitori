import type {
  Attempt,
  Capabilities,
  Chunk,
  Exercise,
  ExerciseAnswer,
  Job,
  Project,
  ProjectStats,
  ProviderStatus,
  RuntimeSettings,
  Waveform,
  SegmentationMetrics,
  Speaker,
} from "../types/api";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly detail?: Record<string, unknown>,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(body.code ?? "REQUEST_FAILED", body.message ?? "Có lỗi xảy ra", body.detail);
  }
  return body as T;
}

export const api = {
  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (payload: { title: string; source_type: "upload" | "youtube"; source_url?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (id: string, payload: Partial<Pick<Project, "title">>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  uploadMedia: (projectId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ asset_id: string; duration_ms: number; sha256: string; original_name?: string; mime_type?: string; size_bytes?: number; metadata?: Record<string, unknown> }>(`/projects/${projectId}/media/upload`, {
      method: "POST",
      body,
    });
  },
  importYoutube: (projectId: string, url: string) =>
    request<{ asset_id: string; duration_ms: number; sha256: string; original_name?: string; metadata?: Record<string, unknown> }>(`/projects/${projectId}/media/youtube`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  processProject: (
    projectId: string,
    payload: { segmentation_preset: "fewer" | "balanced" | "short"; num_speakers?: number; force?: boolean; stages?: string[]; vad_threshold?: number; min_speech_ms?: number; min_silence_ms?: number; speech_pad_ms?: number; merge_gap_ms?: number; target_chunk_ms?: number; max_chunk_ms?: number },
  ) => request<Job>(`/projects/${projectId}/process`, { method: "POST", body: JSON.stringify(payload) }),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),
  retryJob: (id: string) => request<Job>(`/jobs/${id}/retry`, { method: "POST" }),
  listChunks: (projectId: string) => request<Chunk[]>(`/projects/${projectId}/chunks`),
  listPracticeChunks: (projectId: string) => request<Chunk[]>(`/projects/${projectId}/practice-chunks`),
  listMedia: (projectId: string) => request<{ id: string; kind: string; original_name?: string | null; mime_type?: string | null; size_bytes: number; duration_ms?: number | null; sample_rate?: number | null; channels?: number | null; sha256?: string | null; metadata: Record<string, unknown> }[]>(`/projects/${projectId}/media`),
  listSpeakers: (projectId: string) => request<Speaker[]>(`/projects/${projectId}/speakers`),
  createSpeaker: (projectId: string, payload: { label: string; display_name?: string; color?: string }) => request<Speaker>(`/projects/${projectId}/speakers`, { method: "POST", body: JSON.stringify(payload) }),
  updateSpeaker: (id: string, payload: { display_name?: string; color?: string }) => request<Speaker>(`/speakers/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  getWaveform: (projectId: string) => request<Waveform>(`/projects/${projectId}/waveform`),
  getMetrics: (projectId: string) => request<SegmentationMetrics>(`/projects/${projectId}/segmentation-metrics`),
  updateChunk: (id: string, payload: Partial<Pick<Chunk, "start_ms" | "end_ms" | "speaker_id" | "status">> & { expected_boundary_revision?: number }) =>
    request<Chunk>(`/chunks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  splitChunk: (id: string, at_ms: number, expected_boundary_revision: number) =>
    request<Chunk[]>(`/chunks/${id}/split`, {
      method: "POST",
      body: JSON.stringify({ at_ms, expected_boundary_revision }),
    }),
  mergeChunks: (chunk_ids: string[], expected_project_revision: number) =>
    request<Chunk>("/chunks/merge", {
      method: "POST",
      body: JSON.stringify({ chunk_ids, expected_project_revision }),
    }),
  updateReference: (id: string, reference_text: string, confirm = true) =>
    request<Chunk>(`/chunks/${id}/reference`, {
      method: "PUT",
      body: JSON.stringify({ reference_text, confirm }),
    }),
  updateTranslation: (id: string, translation_vi: string, confirm = true) => request<Chunk>(`/chunks/${id}/translation`, { method: "PUT", body: JSON.stringify({ translation_vi, confirm }) }),
  updateFurigana: (id: string, furigana: unknown[], confirm = true) => request<Chunk>(`/chunks/${id}/furigana`, { method: "PUT", body: JSON.stringify({ furigana, confirm }) }),
  reprocessChunk: (id: string, stages: string[]) =>
    request<Job>(`/chunks/${id}/reprocess`, { method: "POST", body: JSON.stringify({ stages, chunk_ids: [id] }) }),
  reorderChunks: (projectId: string, ordered_chunk_ids: string[], expected_project_revision: number) => request<Chunk[]>(`/projects/${projectId}/chunks/reorder`, { method: "POST", body: JSON.stringify({ ordered_chunk_ids, expected_project_revision }) }),
  deleteChunk: (id: string, expected_project_revision?: number) => request<void>(`/chunks/${id}${expected_project_revision ? `?expected_project_revision=${expected_project_revision}` : ""}`, { method: "DELETE" }),
  generateExercises: (
    projectId: string,
    payload: { mode: "full" | "cloze"; chunk_ids?: string[]; settings?: Record<string, unknown> },
  ) => request<Exercise[]>(`/projects/${projectId}/exercises/generate`, { method: "POST", body: JSON.stringify(payload) }),
  listExercises: (projectId: string, mode?: "full" | "cloze") =>
    request<Exercise[]>(`/projects/${projectId}/practice-session${mode ? `?mode=${mode}` : ""}`),
  getExerciseAnswer: (id: string) => request<ExerciseAnswer>(`/exercises/${id}/answer`),
  updateExercise: (id: string, payload: { is_difficult?: boolean; blank_spec?: Record<string, unknown> }) =>
    request<Exercise>(`/exercises/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  submitAttempt: (
    id: string,
    payload: { answer_text?: string; blank_answers?: string[]; revealed_answer?: boolean; duration_ms?: number },
  ) => request<Attempt>(`/exercises/${id}/attempts`, { method: "POST", body: JSON.stringify(payload) }),
  getStats: (projectId: string) => request<ProjectStats>(`/projects/${projectId}/stats`),
  exportProject: (projectId: string, includeAudio = false) => request<{ filename: string; download_url: string }>(`/projects/${projectId}/export`, { method: "POST", body: JSON.stringify({ include_audio: includeAudio, include_attempts: true }) }),
  cleanupProject: (projectId: string) => request<{ removed_files: number; removed_bytes: number; removed_cache_files: number }>(`/projects/${projectId}/cleanup`, { method: "POST" }),
  capabilities: () => request<Capabilities>("/system/capabilities"),
  modelStatus: () => request<ProviderStatus[]>("/models/status"),
  getSettings: () => request<RuntimeSettings>("/settings"),
  updateSettings: (payload: Partial<RuntimeSettings>) =>
    request<RuntimeSettings>("/settings", { method: "PUT", body: JSON.stringify(payload) }),
  mediaUrl: (projectId: string) => `/api/projects/${projectId}/media/stream`,
};

export function subscribeToJob(jobId: string, onJob: (job: Job) => void, onError: (error: Error) => void): () => void {
  const stream = new EventSource(`/api/jobs/${jobId}/events`);
  let pollTimer: number | undefined;
  let polling = false;
  stream.addEventListener("job", (event) => onJob(JSON.parse((event as MessageEvent).data) as Job));
  stream.onerror = () => {
    if (polling) return;
    polling = true;
    stream.close();
    onError(new Error("SSE mất kết nối; đang chuyển sang polling"));
    const poll = async () => {
      try {
        const job = await api.getJob(jobId);
        onJob(job);
        if (["succeeded", "failed", "cancelled"].includes(job.status)) return;
      } catch {
        // Keep retrying while the worker is alive.
      }
      pollTimer = window.setTimeout(() => void poll(), 1500);
    };
    void poll();
  };
  return () => { stream.close(); if (pollTimer !== undefined) window.clearTimeout(pollTimer); };
}
