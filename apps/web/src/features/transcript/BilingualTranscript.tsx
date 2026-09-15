import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useAudio } from "../../components/AudioProvider";
import RubyText from "../../components/RubyText";
import { formatTime } from "../../lib/format";
import type { Chunk, Speaker } from "../../types/api";

export default function BilingualTranscript({ projectId, chunks, speakers }: { projectId: string; chunks: Chunk[]; speakers: Speaker[] }) {
  const queryClient = useQueryClient();
  const audio = useAudio();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const filtered = useMemo(() => chunks.filter((chunk) => {
    const text = `${chunk.text?.reference_text ?? ""} ${chunk.text?.translation_vi ?? ""} ${chunk.text?.asr_normalized ?? ""}`;
    return !query.trim() || text.toLowerCase().includes(query.toLowerCase());
  }), [chunks, query]);
  return <section className="card card-pad stack">
    <div className="row between wrap"><div><h2>Transcript song ngữ</h2><p className="muted small">Bấm một dòng để nghe; transcript user-confirmed được giữ nguyên khi chạy lại AI.</p></div><input className="input search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm tiếng Nhật hoặc tiếng Việt…" /></div>
    <div className="transcript-list">{filtered.map((chunk) => <TranscriptRow key={chunk.id} projectId={projectId} chunk={chunk} speakers={speakers} selected={selected === chunk.id} onSelect={() => { setSelected(chunk.id); audio.seek(chunk.start_ms); }} onSaved={() => { void queryClient.invalidateQueries({ queryKey: ["chunks", projectId, "transcript"] }); }} />)}{filtered.length === 0 ? <div className="empty">Không có dòng phù hợp.</div> : null}</div>
  </section>;
}

function TranscriptRow({ chunk, speakers, selected, onSelect, onSaved }: { projectId: string; chunk: Chunk; speakers: Speaker[]; selected: boolean; onSelect: () => void; onSaved: () => void }) {
  const [draft, setDraft] = useState(chunk.text?.reference_text ?? "");
  const [translation, setTranslation] = useState(chunk.text?.translation_vi ?? "");
  const [saving, setSaving] = useState(false);
  const speaker = speakers.find((item) => item.id === chunk.speaker_id) ?? chunk.speaker;
  async function save() {
    if (!draft.trim() || draft.trim() === chunk.text?.reference_text?.trim()) return;
    setSaving(true);
    try { await api.updateReference(chunk.id, draft.trim(), true); onSaved(); } finally { setSaving(false); }
  }
  async function saveTranslation() {
    if (!translation.trim() || translation.trim() === chunk.text?.translation_vi?.trim()) return;
    setSaving(true);
    try { await api.updateTranslation(chunk.id, translation.trim(), true); onSaved(); } finally { setSaving(false); }
  }
  return <article className={`transcript-row ${selected ? "selected" : ""}`} onClick={onSelect}>
    <div className="transcript-gutter"><button className="chunk-index" onClick={(event) => { event.stopPropagation(); onSelect(); }}>{chunk.order_index + 1}</button><span className="speaker-dot" style={{ background: speaker?.color }} /><span className="muted small">{formatTime(chunk.start_ms)}–{formatTime(chunk.end_ms)}</span></div>
    <div className="transcript-japanese">{chunk.text?.furigana_status === "ready" ? <RubyText tokens={chunk.text.furigana} fallback={chunk.text.reference_text} /> : <span>{chunk.text?.reference_text || chunk.text?.asr_normalized || "Chưa có transcript"}</span>}<textarea className="textarea transcript-edit" value={draft} onChange={(event) => setDraft(event.target.value)} onBlur={() => void save()} placeholder="Nhập transcript tiếng Nhật…" />{saving ? <span className="muted small">Đang lưu…</span> : null}</div>
    <div className="transcript-vietnamese"><textarea className="textarea transcript-edit" value={translation} onChange={(event) => setTranslation(event.target.value)} onBlur={() => void saveTranslation()} placeholder="Bản dịch tiếng Việt…" /><span className={`badge ${chunk.text?.translation_status === "ready" || chunk.text?.translation_status === "user_confirmed" ? "ready" : ""}`}>{chunk.text?.translation_status ?? "missing"}</span></div>
  </article>;
}
