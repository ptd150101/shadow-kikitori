import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { api, ApiError } from "../../api/client";
import { useAudio } from "../../components/AudioProvider";
import RubyText from "../../components/RubyText";
import WaveformTimeline from "../../components/WaveformTimeline";
import { formatTime } from "../../lib/format";
import type { Chunk, Waveform } from "../../types/api";
import "./timeline.css";

type BoundaryEdit = { chunkId: string; before: Pick<Chunk, "start_ms" | "end_ms">; after: Pick<Chunk, "start_ms" | "end_ms"> };

export default function ChunkEditor({ projectId, projectRevision, chunks, waveform }: { projectId: string; projectRevision: number; chunks: Chunk[]; waveform: Waveform }) {
  const queryClient = useQueryClient();
  const audio = useAudio();
  const scrollRef = useRef<HTMLDivElement>(null);
  const history = useRef<BoundaryEdit[]>([]);
  const redoHistory = useRef<BoundaryEdit[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(chunks[0]?.id ?? null);
  const [drafts, setDrafts] = useState<Record<string, Partial<Pick<Chunk, "start_ms" | "end_ms">>>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const displayChunks = useMemo(() => chunks.map((chunk) => ({ ...chunk, ...drafts[chunk.id] })), [chunks, drafts]);
  const selected = displayChunks.find((chunk) => chunk.id === selectedId) ?? displayChunks[0] ?? null;
  const virtualizer = useVirtualizer({ count: displayChunks.length, getScrollElement: () => scrollRef.current, estimateSize: () => 148, overscan: 8 });

  useEffect(() => {
    if (selectedId && chunks.some((chunk) => chunk.id === selectedId)) return;
    setSelectedId(chunks[0]?.id ?? null);
  }, [chunks, selectedId]);

  function refresh() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["chunks", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["project", projectId] }),
    ]);
  }

  async function commitBoundary(chunkId: string) {
    const draft = drafts[chunkId];
    const original = chunks.find((chunk) => chunk.id === chunkId);
    if (!draft || !original || (draft.start_ms === undefined && draft.end_ms === undefined)) return;
    const after = { start_ms: draft.start_ms ?? original.start_ms, end_ms: draft.end_ms ?? original.end_ms };
    if (after.start_ms === original.start_ms && after.end_ms === original.end_ms) {
      setDrafts((current) => { const next = { ...current }; delete next[chunkId]; return next; });
      return;
    }
    setBusy(true); setError(null);
    try {
      await api.updateChunk(chunkId, { ...after, expected_boundary_revision: original.boundary_revision });
      history.current.push({ chunkId, before: { start_ms: original.start_ms, end_ms: original.end_ms }, after });
      redoHistory.current = [];
      setDrafts((current) => { const next = { ...current }; delete next[chunkId]; return next; });
      await refresh();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Không lưu được biên chunk.");
      setDrafts((current) => { const next = { ...current }; delete next[chunkId]; return next; });
    } finally { setBusy(false); }
  }

  async function undo() {
    const command = history.current.pop();
    const current = chunks.find((chunk) => chunk.id === command?.chunkId);
    if (!command || !current) return;
    setBusy(true);
    try {
      await api.updateChunk(command.chunkId, { ...command.before, expected_boundary_revision: current.boundary_revision });
      redoHistory.current.push(command);
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể undo."); history.current.push(command); }
    finally { setBusy(false); }
  }

  async function redo() {
    const command = redoHistory.current.pop();
    const current = chunks.find((chunk) => chunk.id === command?.chunkId);
    if (!command || !current) return;
    setBusy(true);
    try {
      await api.updateChunk(command.chunkId, { ...command.after, expected_boundary_revision: current.boundary_revision });
      history.current.push(command);
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể redo."); redoHistory.current.push(command); }
    finally { setBusy(false); }
  }

  async function splitAtPlayhead() {
    if (!selected || audio.currentMs <= selected.start_ms || audio.currentMs >= selected.end_ms) {
      setError("Đặt playhead nằm bên trong chunk trước khi split."); return;
    }
    setBusy(true); setError(null);
    try {
      const parts = await api.splitChunk(selected.id, audio.currentMs, selected.boundary_revision);
      setSelectedId(parts[1]?.id ?? parts[0]?.id ?? null);
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể split chunk."); }
    finally { setBusy(false); }
  }

  async function mergeWithNext() {
    if (!selected) return;
    const index = chunks.findIndex((chunk) => chunk.id === selected.id);
    const next = chunks[index + 1];
    if (!next) return setError("Đây là chunk cuối cùng.");
    setBusy(true); setError(null);
    try {
      const merged = await api.mergeChunks([selected.id, next.id], projectRevision);
      setSelectedId(merged.id);
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể merge chunk."); }
    finally { setBusy(false); }
  }

  async function changeSpeaker(chunk: Chunk, speakerId: string) {
    setBusy(true);
    try {
      await api.updateChunk(chunk.id, { speaker_id: speakerId || null, expected_boundary_revision: chunk.boundary_revision });
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể đổi speaker."); }
    finally { setBusy(false); }
  }

  async function moveChunk(chunkId: string, direction: -1 | 1) {
    const index = chunks.findIndex((item) => item.id === chunkId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= chunks.length) return;
    const ordered = chunks.map((item) => item.id);
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setBusy(true); setError(null);
    try { await api.reorderChunks(projectId, ordered, projectRevision); await refresh(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể đổi thứ tự chunk."); }
    finally { setBusy(false); }
  }

  async function removeSelected(chunk: Chunk) {
    if (!window.confirm(`Xóa chunk ${chunk.order_index + 1}? Audio gốc vẫn được giữ.`)) return;
    setBusy(true); setError(null);
    try { await api.deleteChunk(chunk.id, projectRevision); setSelectedId(null); await refresh(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không thể xóa chunk."); }
    finally { setBusy(false); }
  }

  async function saveReference(chunk: Chunk, value: string) {
    if (!value.trim() || value.trim() === chunk.text?.reference_text?.trim()) return;
    try {
      await api.updateReference(chunk.id, value.trim(), true);
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Không lưu được transcript."); }
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing = target?.matches("input, textarea, select") || target?.isContentEditable;
      if (typing) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) void redo(); else void undo();
      }
      if (event.key.toLowerCase() === "s") { event.preventDefault(); void splitAtPlayhead(); }
      if (event.key.toLowerCase() === "m") { event.preventDefault(); void mergeWithNext(); }
      if (event.key === "[" && selected) setDrafts((drafts) => ({ ...drafts, [selected.id]: { ...drafts[selected.id], start_ms: audio.currentMs } }));
      if (event.key === "]" && selected) setDrafts((drafts) => ({ ...drafts, [selected.id]: { ...drafts[selected.id], end_ms: audio.currentMs } }));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const speakers = Array.from(new Map(chunks.flatMap((chunk) => chunk.speaker ? [[chunk.speaker.id, chunk.speaker] as const] : [])).values());
  return <div className="stack">
    {error ? <div className="notice error">{error}</div> : null}
    <section className="card card-pad stack">
      <div className="row between wrap">
        <div><h2>Audio editor</h2><p className="muted small">Kéo hai biên của chunk đang chọn trên timeline. S = split, M = merge, Ctrl+Z = undo.</p></div>
        <div className="row wrap">
          <button className="button small" onClick={() => void undo()} disabled={busy || history.current.length === 0}>Undo</button>
          <button className="button small" onClick={() => void redo()} disabled={busy || redoHistory.current.length === 0}>Redo</button>
          <button className="button small" onClick={() => void splitAtPlayhead()} disabled={!selected || busy}>Split tại playhead</button>
          <button className="button small" onClick={() => void mergeWithNext()} disabled={!selected || busy}>Merge tiếp theo</button>
          {selected ? <button className="button primary small" onClick={() => void audio.playRange(selected.start_ms, selected.end_ms, true)}>Loop chunk</button> : null}
        </div>
      </div>
      <WaveformTimeline
        waveform={waveform}
        chunks={displayChunks}
        selectedChunkId={selected?.id ?? null}
        currentMs={audio.currentMs}
        onSelectChunk={setSelectedId}
        onSeek={audio.seek}
        onPreviewBoundary={(id, values) => setDrafts((current) => ({ ...current, [id]: { ...current[id], ...values } }))}
        onCommitBoundary={(id) => void commitBoundary(id)}
      />
    </section>
    <section className="card chunk-list" ref={scrollRef}>
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((item) => {
          const chunk = displayChunks[item.index];
          const original = chunks[item.index];
          return <div key={chunk.id} ref={virtualizer.measureElement} data-index={item.index} className="chunk-virtual-row" style={{ transform: `translateY(${item.start}px)` }}>
            <ChunkRow
              chunk={chunk}
              original={original}
              waveform={waveform}
              selected={chunk.id === selected?.id}
              speakers={speakers}
              onSelect={() => { setSelectedId(chunk.id); audio.seek(chunk.start_ms); }}
              onPlay={() => void audio.playRange(chunk.start_ms, chunk.end_ms, false)}
              onSpeaker={(speakerId) => void changeSpeaker(original, speakerId)}
              onReference={(value) => void saveReference(original, value)}
              onReprocess={() => api.reprocessChunk(chunk.id, ["asr", "furigana", "translation"]).then(() => setError("Đã đưa chunk vào hàng đợi reprocess."))}
              onMoveUp={() => void moveChunk(chunk.id, -1)}
              onMoveDown={() => void moveChunk(chunk.id, 1)}
              onDelete={() => void removeSelected(chunk)}
            />
          </div>;
        })}
      </div>
    </section>
  </div>;
}

function ChunkRow({ chunk, original, waveform, selected, speakers, onSelect, onPlay, onSpeaker, onReference, onReprocess, onMoveUp, onMoveDown, onDelete }: {
  chunk: Chunk;
  original: Chunk;
  waveform: Waveform;
  selected: boolean;
  speakers: { id: string; display_name: string; color: string }[];
  onSelect: () => void;
  onPlay: () => void;
  onSpeaker: (speakerId: string) => void;
  onReference: (value: string) => void;
  onReprocess: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState(chunk.text?.reference_text ?? "");
  useEffect(() => setDraft(chunk.text?.reference_text ?? ""), [chunk.id, chunk.text?.reference_text]);
  return <article className={`chunk-row ${selected ? "selected" : ""}`} onClick={onSelect}>
    <div className="chunk-meta">
      <button className="chunk-index" onClick={(event) => { event.stopPropagation(); onPlay(); }}>{chunk.order_index + 1}</button>
      <span className="speaker-dot" style={{ background: chunk.speaker?.color }} />
      <select className="speaker-select" value={chunk.speaker_id ?? ""} onClick={(event) => event.stopPropagation()} onChange={(event) => onSpeaker(event.target.value)}>
        <option value="">Speaker</option>{speakers.map((speaker) => <option value={speaker.id} key={speaker.id}>{speaker.display_name}</option>)}
      </select>
      <span className="muted small">{formatTime(chunk.start_ms)}–{formatTime(chunk.end_ms)} · {((chunk.end_ms - chunk.start_ms) / 1000).toFixed(1)}s</span>
      <span className={`badge ${chunk.text?.reference_status === "user_confirmed" ? "ready" : chunk.text?.reference_status === "stale" ? "stale" : ""}`}>{chunk.text?.reference_status ?? "missing"}</span>
    </div>
    <MiniWaveform waveform={waveform} start={chunk.start_ms} end={chunk.end_ms} color={chunk.speaker?.color ?? "#60a5fa"} />
    <div className="chunk-content" onClick={(event) => event.stopPropagation()}>
      {chunk.text?.furigana_status === "ready" ? <RubyText className="ruby small" tokens={chunk.text.furigana} fallback={chunk.text.reference_text} /> : null}
      <textarea className="textarea chunk-transcript" value={draft} onChange={(event) => setDraft(event.target.value)} onBlur={() => onReference(draft)} placeholder="Transcript tiếng Nhật…" />
      <div className="row wrap"><button className="button small" onClick={onPlay}>Nghe</button><button className="button ghost small" onClick={onReprocess}>Re-run AI</button><button className="button ghost small" onClick={onMoveUp} aria-label="Đưa chunk lên">↑</button><button className="button ghost small" onClick={onMoveDown} aria-label="Đưa chunk xuống">↓</button><button className="button danger small" onClick={onDelete}>Xóa</button>{original.boundary_revision !== chunk.boundary_revision ? <span className="muted small">Chưa lưu biên</span> : null}</div>
    </div>
  </article>;
}

function MiniWaveform({ waveform, start, end, color }: { waveform: Waveform; start: number; end: number; color: string }) {
  const duration = waveform.duration_ms || 1;
  const from = Math.floor((start / duration) * waveform.peaks.length);
  const to = Math.max(from + 1, Math.ceil((end / duration) * waveform.peaks.length));
  const source = waveform.peaks.slice(from, to);
  const stride = Math.max(1, Math.ceil(source.length / 96));
  const peaks = source.filter((_, index) => index % stride === 0);
  return <svg className="mini-wave" preserveAspectRatio="none" viewBox={`0 0 ${Math.max(peaks.length, 1)} 50`}>
    {peaks.map(([min, max], index) => <line key={index} x1={index + .5} x2={index + .5} y1={(1 - max) * 25} y2={(1 - min) * 25} stroke={color} />)}
  </svg>;
}
