import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Navigate, useLocation, useParams } from "react-router-dom";
import { api } from "../../api/client";
import AudioTransport from "../../components/AudioTransport";
import { AudioProvider } from "../../components/AudioProvider";
import ChunkEditor from "../timeline/ChunkEditor";
import PracticePage from "../practice/PracticePage";
import BilingualTranscript from "../transcript/BilingualTranscript";
import { formatDuration } from "../../lib/format";

type Tab = "editor" | "transcript" | "practice" | "insights";

export default function WorkspacePage() {
  const { projectId = "" } = useParams();
  const location = useLocation();
  const queryClient = useQueryClient();
  const tab = (location.pathname.split("/").pop() as Tab) || "editor";
  const activeTab: Tab = ["editor", "transcript", "practice", "insights"].includes(tab) ? tab : "editor";
  const [error, setError] = useState<string | null>(null);
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api.getProject(projectId), enabled: Boolean(projectId) });
  const chunks = useQuery({ queryKey: ["chunks", projectId, activeTab], queryFn: () => activeTab === "practice" ? api.listPracticeChunks(projectId) : api.listChunks(projectId), enabled: Boolean(projectId) });
  const waveform = useQuery({ queryKey: ["waveform", projectId], queryFn: () => api.getWaveform(projectId), enabled: Boolean(projectId) && activeTab === "editor" });
  const metrics = useQuery({ queryKey: ["metrics", projectId], queryFn: () => api.getMetrics(projectId), enabled: Boolean(projectId) && activeTab === "insights" });
  const speakers = useQuery({ queryKey: ["speakers", projectId], queryFn: () => api.listSpeakers(projectId), enabled: Boolean(projectId) });

  const source = useMemo(() => api.mediaUrl(projectId), [projectId]);
  if (project.isLoading) return <div className="empty">Đang mở workspace…</div>;
  if (!project.data) return <div className="notice error">Không tìm thấy project.</div>;
  if (project.data.status === "draft") {
    return <Navigate to={`/projects/${projectId}/import`} replace />;
  }
  const title = project.data.title;
  return <AudioProvider source={source}>
    <section className="page stack workspace-page">
      <header className="page-header workspace-header">
        <div>
          <Link className="muted small" to="/projects">← Thư viện</Link>
          <h1>{title}</h1>
          <p className="muted">{formatDuration(project.data.duration_ms)} · {project.data.chunk_count} chunks · revision {project.data.active_revision}</p>
        </div>
        <div className="row wrap">
          <button className="button" onClick={() => api.exportProject(projectId).then((item) => { window.location.href = item.download_url; }).catch(() => setError("Không thể export project."))}>Export JSON</button>
          <button className="button ghost" onClick={() => api.exportProject(projectId, true).then((item) => { window.location.href = item.download_url; }).catch(() => setError("Không thể export archive."))}>JSON + audio</button>
          <Link className="button" to={`/projects/${projectId}/import`}>Xử lý lại</Link>
        </div>
      </header>
      {error ? <div className="notice error">{error}</div> : null}
      <nav className="workspace-tabs tabs" aria-label="Workspace tabs">
        {(["editor", "transcript", "practice", "insights"] as Tab[]).map((item) => <NavLink key={item} className={({ isActive }) => isActive ? "active" : ""} to={`/projects/${projectId}/${item}`}>{item === "editor" ? "Audio editor" : item === "transcript" ? "Transcript + dịch" : item === "practice" ? "Luyện tập" : "Phân tích"}</NavLink>)}
      </nav>
      {activeTab === "editor" && waveform.data && chunks.data ? <ChunkEditor projectId={projectId} projectRevision={project.data.active_revision} chunks={chunks.data} waveform={waveform.data} /> : null}
      {activeTab === "editor" && (!waveform.data || !chunks.data) ? <div className="card empty">{waveform.isLoading || chunks.isLoading ? "Đang tải timeline…" : "Chưa có waveform/chunk. Hãy chạy xử lý AI."}</div> : null}
      {activeTab === "transcript" && chunks.data ? <BilingualTranscript projectId={projectId} chunks={chunks.data} speakers={speakers.data ?? []} /> : null}
      {activeTab === "transcript" && !chunks.data ? <div className="card empty">Đang tải transcript…</div> : null}
      {activeTab === "practice" ? <PracticePage projectId={projectId} /> : null}
      {activeTab === "insights" ? <Insights projectId={projectId} metrics={metrics.data} onRefresh={() => { void queryClient.invalidateQueries({ queryKey: ["metrics", projectId] }); }} /> : null}
      {activeTab !== "practice" ? <SpeakerPanel projectId={projectId} speakers={speakers.data ?? []} onChanged={() => { void queryClient.invalidateQueries({ queryKey: ["speakers", projectId] }); void queryClient.invalidateQueries({ queryKey: ["chunks", projectId, activeTab] }); }} /> : null}
      <AudioTransport />
    </section>
  </AudioProvider>;
}

function Insights({ projectId, metrics, onRefresh }: { projectId: string; metrics?: Awaited<ReturnType<typeof api.getMetrics>>; onRefresh: () => void }) {
  const stats = useQuery({ queryKey: ["stats", projectId], queryFn: () => api.getStats(projectId) });
  return <div className="grid two">
    <section className="card card-pad stack"><div className="row between"><h2>Segmentation QA</h2><button className="button small" onClick={onRefresh}>Refresh</button></div>{metrics ? <div className="metric-grid"><Metric label="Chunks" value={metrics.chunk_count} /><Metric label="Vùng speech" value={metrics.vad_region_count} /><Metric label="Mean" value={`${(metrics.mean_chunk_ms / 1000).toFixed(1)}s`} /><Metric label="P95" value={`${(metrics.p95_chunk_ms / 1000).toFixed(1)}s`} /><Metric label="Chunk ngắn" value={metrics.short_chunk_count} /><Metric label="Speaker" value={metrics.speaker_count} /></div> : <p className="muted">Đang tải metrics…</p>}</section>
    <section className="card card-pad stack"><h2>Tiến độ luyện</h2>{stats.data ? <div className="metric-grid"><Metric label="Bài luyện" value={stats.data.exercise_count} /><Metric label="Lượt làm" value={stats.data.attempt_count} /><Metric label="Điểm TB" value={`${stats.data.average_score.toFixed(1)}%`} /><Metric label="Đánh dấu khó" value={stats.data.difficult_count} /></div> : <p className="muted">Đang tải thống kê…</p>}<p className="muted small">Metrics giúp phát hiện chunk quá ngắn/quá dài trước khi luyện; sửa lại biên trong Audio editor.</p><button className="button small" onClick={() => api.cleanupProject(projectId).then((result) => window.alert(`Đã dọn ${result.removed_cache_files} file cache.`))}>Dọn chunk cache</button></section>
  </div>;
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div className="metric"><span className="muted small">{label}</span><strong>{value}</strong></div>; }

function SpeakerPanel({ projectId, speakers, onChanged }: { projectId: string; speakers: { id: string; label: string; display_name: string; color: string }[]; onChanged: () => void }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [newLabel, setNewLabel] = useState("");
  return <section className="card card-pad stack speaker-panel"><div className="row between"><div><h2>Speaker labels</h2><p className="muted small">Đổi tên hoặc màu để đọc hội thoại dễ hơn; nhãn diarization gốc vẫn được giữ.</p></div></div><div className="speaker-grid">{speakers.map((speaker) => <div className="speaker-editor row" key={speaker.id}><span className="speaker-dot" style={{ background: speaker.color }} /><input className="input" value={drafts[speaker.id] ?? speaker.display_name} onChange={(event) => setDrafts({ ...drafts, [speaker.id]: event.target.value })} onBlur={() => { const value = drafts[speaker.id]?.trim(); if (value && value !== speaker.display_name) { void api.updateSpeaker(speaker.id, { display_name: value }).then(onChanged); } }} /><input type="color" value={speaker.color} onChange={(event) => { void api.updateSpeaker(speaker.id, { color: event.target.value }).then(onChanged); }} /></div>)}</div><div className="row wrap"><input className="input" value={newLabel} onChange={(event) => setNewLabel(event.target.value)} placeholder="SPEAKER_02" /><button className="button small" onClick={() => { if (newLabel.trim()) { void api.createSpeaker(projectId, { label: newLabel.trim() }).then(() => { setNewLabel(""); onChanged(); }); } }}>Thêm speaker</button></div></section>;
}
