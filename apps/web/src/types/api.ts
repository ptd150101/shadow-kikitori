export type Project = {
  id: string;
  title: string;
  source_type: "upload" | "youtube";
  source_url: string | null;
  status: string;
  language: string;
  active_revision: number;
  last_opened_at: string | null;
  pipeline_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  duration_ms: number | null;
  chunk_count: number;
};

export type Job = {
  id: string;
  project_id: string;
  type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancel_requested" | "cancelled" | "interrupted";
  stage: string;
  progress_0_100: number;
  message: string;
  attempt: number;
  max_attempts: number;
  error_code: string | null;
  error_detail: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type Speaker = {
  id: string;
  label: string;
  display_name: string;
  color: string;
  is_manual: boolean;
};

export type FuriganaToken = {
  surface: string;
  reading?: string | null;
  ruby?: boolean;
  part_of_speech?: string | null;
};

export type ChunkText = {
  asr_raw?: string | null;
  asr_normalized?: string | null;
  reference_text?: string | null;
  reference_status: string;
  furigana?: FuriganaToken[] | null;
  furigana_status: string;
  translation_vi?: string | null;
  translation_status: string;
};

export type Chunk = {
  id: string;
  project_id: string;
  speaker_id: string | null;
  order_index: number;
  start_ms: number;
  end_ms: number;
  source: string;
  status: string;
  boundary_revision: number;
  speaker?: Speaker | null;
  text?: ChunkText | null;
};

export type Waveform = {
  sample_rate: number;
  duration_ms: number;
  points?: number;
  peaks: [number, number][];
};

export type Exercise = {
  id: string;
  project_id: string;
  chunk_id: string;
  mode: "full" | "cloze";
  blank_spec: {
    version?: number;
    blank_token_indexes?: number[];
    tokens?: FuriganaToken[];
    blank_count?: number;
  };
  settings: Record<string, unknown>;
  reference_revision: number;
  status: string;
  is_difficult: boolean;
  reference_status: string;
  chunk?: Chunk | null;
};

export type AnswerBundle = {
  reference_text: string;
  furigana?: FuriganaToken[] | null;
  translation_vi?: string | null;
  cloze_expected: string[];
  reference_confirmed: boolean;
};

export type ExerciseAnswer = {
  exercise_id: string;
  chunk_id: string;
  mode: "full" | "cloze";
  reference_text: string;
  furigana?: FuriganaToken[] | null;
  translation_vi?: string | null;
  blank_spec: { version?: number; blank_token_indexes?: number[]; tokens?: FuriganaToken[] };
  reference_confirmed: boolean;
  cloze_expected?: string[];
};

export type Attempt = {
  id: string;
  exercise_id: string;
  answer_text: string;
  score: number | null;
  strict_score: number | null;
  diff: { kind: string; text?: string; expected?: string; actual?: string; index?: string; score?: string }[];
  revealed_answer: boolean;
  duration_ms: number | null;
  created_at: string;
  answer?: AnswerBundle | null;
};

export type Capabilities = {
  ffmpeg: boolean;
  ffprobe: boolean;
  ytdlp: boolean;
  cuda_available: boolean;
  data_dir: string;
  platform?: string | null;
  max_upload_bytes?: number | null;
  max_duration_seconds?: number | null;
};

export type ProviderStatus = { name: string; ready: boolean; detail: string };

export type RuntimeSettings = {
  ffmpeg_path: string;
  ffprobe_path: string;
  ytdlp_path: string;
  audio8_model_id: string;
  audio8_revision: string | null;
  pyannote_model_path: string | null;
  device: string;
  llm_mode: string;
  llm_base_url: string;
  llm_model: string;
  llm_executable: string | null;
  llm_model_path: string | null;
  audio8_max_seconds: number;
};

export type ProjectStats = {
  exercise_count: number;
  attempt_count: number;
  average_score: number;
  difficult_count: number;
};

export type SpeakerStatus = Speaker & { is_manual: boolean };

export type SegmentationMetrics = {
  project_id: string;
  chunk_count: number;
  speech_coverage_ms: number;
  silence_coverage_ms: number;
  mean_chunk_ms: number;
  median_chunk_ms: number;
  p95_chunk_ms: number;
  short_chunk_count: number;
  over_target_count: number;
  max_chunk_ms: number;
  vad_region_count: number;
  speaker_count: number;
};
