import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, subscribeToJob } from "../../api/client";
import type { Job } from "../../types/api";
import { formatDuration } from "../../lib/format";

export default function ImportPage() {
  const { projectId = "" } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [preset, setPreset] = useState<"fewer" | "balanced" | "short">("balanced");
  const [numSpeakers, setNumSpeakers] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [vadThreshold, setVadThreshold] = useState("0.5");
  const [minSpeech, setMinSpeech] = useState("250");
  const [minSilence, setMinSilence] = useState("350");
  const [speechPad, setSpeechPad] = useState("150");
  const [mergeGap, setMergeGap] = useState("1200");
  const [job, setJob] = useState<Job | null>(null);
  const [asset, setAsset] = useState<{ original_name?: string; duration_ms?: number; sha256?: string; metadata?: Record<string, unknown> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api.getProject(projectId), enabled: Boolean(projectId) });
  const assets = useQuery({ queryKey: ["media", projectId], queryFn: () => api.listMedia(projectId), enabled: Boolean(projectId) });
  const upload = useMutation({ mutationFn: () => api.uploadMedia(projectId, file!), onSuccess: (next) => { setAsset(next); void queryClient.invalidateQueries({ queryKey: ["media", projectId] }); void queryClient.invalidateQueries({ queryKey: ["project", projectId] }); }, onError: showError });
  const youtube = useMutation({ mutationFn: () => api.importYoutube(projectId, youtubeUrl.trim()), onSuccess: (next) => { setAsset(next); void queryClient.invalidateQueries({ queryKey: ["media", projectId] }); void queryClient.invalidateQueries({ queryKey: ["project", projectId] }); }, onError: showError });
  const process = useMutation({
    mutationFn: () => api.processProject(projectId, {
      segmentation_preset: preset,
      num_speakers: numSpeakers ? Number(numSpeakers) : undefined,
      vad_threshold: advanced ? Number(vadThreshold) : undefined,
      min_speech_ms: advanced ? Number(minSpeech) : undefined,
      min_silence_ms: advanced ? Number(minSilence) : undefined,
      speech_pad_ms: advanced ? Number(speechPad) : undefined,
      merge_gap_ms: advanced ? Number(mergeGap) : undefined,
    }),
    onSuccess: setJob,
    onError: showError,
  });
  const jobId = job?.id;
  const jobStatus = job?.status;

  function showError(reason: unknown) {
    setError(reason instanceof ApiError ? reason.message : "Thao tác thất bại.");
  }

  useEffect(() => {
    if (!jobId || ["succeeded", "failed", "cancelled"].includes(jobStatus ?? "")) return;
    return subscribeToJob(jobId, (next) => {
      setJob(next);
      if (next.status === "succeeded") {
        queryClient.invalidateQueries({ queryKey: ["project", projectId] });
        queryClient.invalidateQueries({ queryKey: ["projects"] });
        queryClient.invalidateQueries({ queryKey: ["chunks", projectId] });
        queryClient.invalidateQueries({ queryKey: ["waveform", projectId] });
      }
    }, () => undefined);
  }, [jobId, jobStatus, projectId, queryClient]);

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setError(null);
  }

  function importFile(event: FormEvent) {
    event.preventDefault();
    if (!file) return setError("Hãy chọn file audio hoặc video.");
    setError(null);
    upload.mutate();
  }

  function importYoutube(event: FormEvent) {
    event.preventDefault();
    if (!youtubeUrl.trim()) return setError("Hãy nhập URL YouTube.");
    setError(null);
    youtube.mutate();
  }

  const imported = Boolean(project.data?.status && project.data.status !== "draft");
  const canProcess = imported && !job;
  return (
    <section className="page stack">
      <header className="page-header">
        <div>
          <Link className="muted small" to="/projects">← Thư viện</Link>
          <h1>{project.data?.title ?? "Import audio"}</h1>
          <p className="muted">Audio sẽ ở local. Upload và YouTube chỉ dùng cho nội dung bạn có quyền sử dụng.</p>
        </div>
      </header>
      {error ? <div className="notice error">{error}</div> : null}
      <div className="grid two">
        <form className="card card-pad stack" onSubmit={importFile}>
          <h2>Upload audio hoặc video</h2>
          <input className="input" type="file" accept="audio/*,video/*,.m4a,.ogg,.flac" onChange={onFile} />
          {file ? <p className="muted small">{file.name} · {Math.round(file.size / 1024 / 1024)} MB</p> : null}
          <button className="button primary" disabled={upload.isPending || !file}>{upload.isPending ? "Đang import…" : "Import file"}</button>
        </form>
        <form className="card card-pad stack" onSubmit={importYoutube}>
          <h2>Import từ YouTube</h2>
          <input className="input" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" />
          <p className="muted small">MVP hỗ trợ một video public, không playlist hoặc video cần đăng nhập.</p>
          <button className="button primary" disabled={youtube.isPending || !youtubeUrl.trim()}>{youtube.isPending ? "Đang tải audio…" : "Import YouTube"}</button>
        </form>
      </div>
      {imported ? (
        <section className="card card-pad stack">
          <div className="row between">
            <div>
              <h2>Chia đoạn và xử lý AI</h2>
              <p className="muted">Source đã import. Chọn segmentation theo độ dài câu bạn muốn luyện.</p>
            </div>
            <span className="badge">{formatDuration(project.data?.duration_ms ?? null)}</span>
          </div>
          {(asset ?? assets.data?.find((item) => item.kind === "source")) ? <div className="import-preview"><strong>{String((asset ?? assets.data?.find((item) => item.kind === "source"))?.metadata?.title ?? (asset ?? assets.data?.find((item) => item.kind === "source"))?.original_name ?? "Media đã import")}</strong><span className="muted small">{formatDuration((asset ?? assets.data?.find((item) => item.kind === "source"))?.duration_ms ?? project.data?.duration_ms ?? null)} · SHA-256 {(asset ?? assets.data?.find((item) => item.kind === "source"))?.sha256?.slice(0, 16)}…</span></div> : null}
          <div className="grid two">
            <label className="label">Preset chia đoạn
              <select className="select" value={preset} onChange={(event) => setPreset(event.target.value as typeof preset)}>
                <option value="fewer">Ít đoạn hơn — câu dài hơn</option>
                <option value="balanced">Cân bằng — mặc định</option>
                <option value="short">Đoạn ngắn — luyện kỹ</option>
              </select>
            </label>
            <label className="label">Số speaker (tuỳ chọn)
              <input className="input" inputMode="numeric" value={numSpeakers} onChange={(event) => setNumSpeakers(event.target.value)} placeholder="Để trống = tự nhận diện" />
            </label>
          </div>
          <details open={advanced} onToggle={(event) => setAdvanced((event.currentTarget as HTMLDetailsElement).open)}>
            <summary className="button ghost small">Advanced VAD / boundary settings</summary>
            <div className="grid four advanced-grid">
              <label className="label">VAD threshold<input className="input" type="number" min="0.05" max="0.99" step="0.05" value={vadThreshold} onChange={(event) => setVadThreshold(event.target.value)} /></label>
              <label className="label">Min speech (ms)<input className="input" type="number" value={minSpeech} onChange={(event) => setMinSpeech(event.target.value)} /></label>
              <label className="label">Min silence (ms)<input className="input" type="number" value={minSilence} onChange={(event) => setMinSilence(event.target.value)} /></label>
              <label className="label">Speech pad (ms)<input className="input" type="number" value={speechPad} onChange={(event) => setSpeechPad(event.target.value)} /></label>
              <label className="label">Merge gap (ms)<input className="input" type="number" value={mergeGap} onChange={(event) => setMergeGap(event.target.value)} /></label>
            </div>
          </details>
          <button className="button primary" onClick={() => process.mutate()} disabled={!canProcess || process.isPending}>{process.isPending ? "Đang tạo job…" : "Bắt đầu xử lý"}</button>
        </section>
      ) : null}
      {job ? <JobProgress job={job} onCancel={() => api.cancelJob(job.id).then(setJob)} onRetry={() => api.retryJob(job.id).then(setJob)} onOpen={() => navigate(`/projects/${projectId}/editor`)} /> : null}
    </section>
  );
}

function JobProgress({ job, onCancel, onRetry, onOpen }: { job: Job; onCancel: () => void; onRetry: () => void; onOpen: () => void }) {
  const done = job.status === "succeeded";
  return <section className="card card-pad stack">
    <div className="row between"><div><h2>{job.message}</h2><p className="muted small">{job.stage} · attempt {job.attempt}/{job.max_attempts}</p></div><strong>{job.progress_0_100}%</strong></div>
    <div className="progress"><span style={{ width: `${job.progress_0_100}%` }} /></div>
    {job.error_detail ? <div className="notice error">{job.error_code}: {job.error_detail}</div> : null}
    <div className="row wrap">
      {job.status === "running" || job.status === "queued" ? <button className="button danger" onClick={onCancel}>Hủy</button> : null}
      {["failed", "cancelled", "interrupted"].includes(job.status) ? <button className="button primary" onClick={onRetry}>Chạy lại</button> : null}
      {done ? <button className="button primary" onClick={onOpen}>Mở audio editor</button> : null}
    </div>
  </section>;
}
