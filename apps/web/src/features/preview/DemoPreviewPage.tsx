import { useMemo, useState } from "react";
import RubyText from "../../components/RubyText";
import { formatTime } from "../../lib/format";
import type { FuriganaToken } from "../../types/api";

type DemoChunk = {
  id: string;
  speaker: string;
  color: string;
  start: number;
  end: number;
  text: string;
  translation: string;
  tokens: FuriganaToken[];
};

const demoChunks: DemoChunk[] = [
  {
    id: "chunk-01",
    speaker: "Speaker A",
    color: "#60a5fa",
    start: 0,
    end: 6_800,
    text: "来週の試験、もう申し込みましたか。",
    translation: "Kỳ thi tuần sau, bạn đã đăng ký chưa?",
    tokens: [
      { surface: "来週", reading: "らいしゅう", ruby: true },
      { surface: "の", ruby: false },
      { surface: "試験", reading: "しけん", ruby: true },
      { surface: "、もう", ruby: false },
      { surface: "申し込み", reading: "もうしこみ", ruby: true },
      { surface: "ましたか。", ruby: false },
    ],
  },
  {
    id: "chunk-02",
    speaker: "Speaker B",
    color: "#f59e0b",
    start: 7_500,
    end: 14_200,
    text: "はい、昨日オンラインで申し込みました。",
    translation: "Rồi, hôm qua tôi đã đăng ký online.",
    tokens: [
      { surface: "はい、", ruby: false },
      { surface: "昨日", reading: "きのう", ruby: true },
      { surface: "オンライン", ruby: false },
      { surface: "で申し込みました。", ruby: false },
    ],
  },
  {
    id: "chunk-03",
    speaker: "Speaker A",
    color: "#60a5fa",
    start: 15_100,
    end: 23_600,
    text: "そうですか。じゃあ、試験の前に一緒に勉強しましょう。",
    translation: "Vậy à. Thế thì trước kỳ thi chúng ta cùng học nhé.",
    tokens: [
      { surface: "そうですか。じゃあ、", ruby: false },
      { surface: "試験", reading: "しけん", ruby: true },
      { surface: "の前", reading: "のまえ", ruby: true },
      { surface: "に一緒", reading: "にいっしょ", ruby: true },
      { surface: "に勉強しましょう。", ruby: false },
    ],
  },
  {
    id: "chunk-04",
    speaker: "Speaker B",
    color: "#f59e0b",
    start: 24_400,
    end: 31_800,
    text: "いいですね。土曜日の午後はどうですか。",
    translation: "Được đấy. Chiều thứ bảy thì thế nào?",
    tokens: [
      { surface: "いいですね。", ruby: false },
      { surface: "土曜日", reading: "どようび", ruby: true },
      { surface: "の午後", reading: "のごご", ruby: true },
      { surface: "はどうですか。", ruby: false },
    ],
  },
];

const waveform = Array.from({ length: 92 }, (_, index) => {
  const wave = Math.abs(Math.sin(index * 0.63) * 0.58 + Math.sin(index * 0.19) * 0.25);
  return Math.max(10, Math.round(wave * 76));
});

export default function DemoPreviewPage() {
  const [tab, setTab] = useState<"editor" | "transcript" | "practice" | "insights">("editor");
  const [selectedId, setSelectedId] = useState(demoChunks[1].id);
  const [playing, setPlaying] = useState(false);
  const [zoom, setZoom] = useState(1.8);
  const selected = demoChunks.find((chunk) => chunk.id === selectedId) ?? demoChunks[0];

  return (
    <section className="preview-page">
      <div className="preview-topbar">
        <div className="row wrap">
          <span className="preview-mark">S</span>
          <div>
            <strong>Shadow Kikitori</strong>
            <span className="preview-subtitle">JLPT N4 · 聴解 practice</span>
          </div>
          <span className="badge preview-badge">DEMO PREVIEW</span>
        </div>
        <div className="row wrap">
          <span className="preview-save"><span className="preview-dot" /> All changes saved</span>
          <button className="button">Export</button>
          <button className="button primary" onClick={() => setPlaying((value) => !value)}>{playing ? "Pause" : "Play project"}</button>
        </div>
      </div>

      <div className="preview-projectbar">
        <div>
          <span className="muted small">PROJECT / MOCK SESSION</span>
          <h1>JLPT N4 · 2024 Listening</h1>
          <p className="muted">4 chunks · 00:31 · 2 speakers · Audio8 transcript</p>
        </div>
        <div className="preview-project-actions">
          <button className="button small">Reprocess</button>
          <button className="button small">Import another audio</button>
        </div>
      </div>

      <nav className="preview-tabs" aria-label="Workspace tabs">
        {(["editor", "transcript", "practice", "insights"] as const).map((item) => (
          <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>
            {item === "editor" ? "Audio editor" : item === "transcript" ? "Bilingual transcript" : item === "practice" ? "Practice" : "Insights"}
          </button>
        ))}
      </nav>

      {tab === "editor" ? <EditorPreview selected={selected} selectedId={selectedId} playing={playing} zoom={zoom} setZoom={setZoom} onSelect={setSelectedId} /> : null}
      {tab === "transcript" ? <TranscriptPreview selectedId={selectedId} onSelect={setSelectedId} /> : null}
      {tab === "practice" ? <PracticePreview selected={selected} /> : null}
      {tab === "insights" ? <InsightsPreview /> : null}

      <div className="preview-transport">
        <button className="button small" onClick={() => setPlaying(false)}>−2s</button>
        <button className="button primary preview-play" onClick={() => setPlaying((value) => !value)}>{playing ? "Ⅱ" : "▶"}</button>
        <button className="button small">+2s</button>
        <div className="preview-progress"><span style={{ width: playing ? "48%" : "34%" }} /></div>
        <span className="muted small">{formatTime(playing ? 15_100 : 9_420)} / 0:31</span>
        <label className="row muted small preview-rate">Speed <select className="select"><option>1×</option><option>0.75×</option><option>1.25×</option></select></label>
      </div>
    </section>
  );
}

function EditorPreview({ selected, selectedId, playing, zoom, setZoom, onSelect }: { selected: DemoChunk; selectedId: string; playing: boolean; zoom: number; setZoom: (value: number) => void; onSelect: (id: string) => void }) {
  return <div className="preview-stack">
    <div className="preview-editor-grid">
      <section className="card card-pad preview-wave-card">
        <div className="row between preview-section-heading"><div><h2>Master timeline</h2><p className="muted small">Drag boundaries or select a chunk to edit its transcript.</p></div><label className="row muted small">Zoom <input type="range" min="1" max="4" step="0.1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label></div>
        <div className="preview-ruler"><span>0:00</span><span>0:08</span><span>0:16</span><span>0:24</span><span>0:31</span></div>
        <div className="preview-master-wave" style={{ transform: `scaleX(${zoom / 1.8})`, transformOrigin: "left center" }}>
          {waveform.map((height, index) => <span key={index} style={{ height: `${height}%`, opacity: index % 9 === 0 ? 1 : .68 }} />)}
          {demoChunks.map((chunk) => <button key={chunk.id} className={`preview-region ${chunk.id === selectedId ? "selected" : ""}`} style={{ left: `${(chunk.start / 31_800) * 100}%`, width: `${((chunk.end - chunk.start) / 31_800) * 100}%`, borderColor: chunk.color, background: `${chunk.color}22` }} onClick={() => onSelect(chunk.id)} aria-label={`Select ${chunk.id}`}><span>{chunk.speaker}</span></button>)}
          <span className="preview-playhead" style={{ left: `${playing ? 48 : 34}%` }} />
        </div>
        <div className="preview-wave-footer"><span className="muted small">VAD speech regions · speaker turns</span><span className="badge ready">4 chunks ready</span></div>
      </section>
      <aside className="card card-pad preview-inspector"><div className="row between"><h2>Selected chunk</h2><span className="badge" style={{ borderColor: selected.color, color: selected.color }}>{selected.speaker}</span></div><div className="preview-time-range"><strong>{formatTime(selected.start)} — {formatTime(selected.end)}</strong><span className="muted small">{((selected.end - selected.start) / 1000).toFixed(1)} seconds</span></div><label className="label">Japanese reference<textarea className="textarea" defaultValue={selected.text} /></label><label className="label">Vietnamese translation<textarea className="textarea" defaultValue={selected.translation} /></label><div className="row wrap"><button className="button primary">Save reference</button><button className="button">Split at playhead</button></div></aside>
    </div>
    <section className="card card-pad"><div className="row between preview-section-heading"><div><h2>Chunk sequence</h2><p className="muted small">Virtualized mini-waveforms · optimistic boundary revisions</p></div><button className="button small">＋ Add speaker</button></div><div className="preview-chunk-list">{demoChunks.map((chunk, index) => <button type="button" key={chunk.id} className={`preview-chunk-row ${chunk.id === selectedId ? "selected" : ""}`} onClick={() => onSelect(chunk.id)}><span className="preview-chunk-number">{String(index + 1).padStart(2, "0")}</span><span className="preview-chunk-speaker"><span className="speaker-dot" style={{ background: chunk.color }} />{chunk.speaker}<small>{formatTime(chunk.start)}–{formatTime(chunk.end)}</small></span><span className="preview-mini-wave">{waveform.slice(index * 15, index * 15 + 15).map((height, item) => <i key={item} style={{ height: `${height}%`, background: chunk.color }} />)}</span><span className="preview-chunk-copy"><RubyText tokens={chunk.tokens} fallback={chunk.text} className="ruby small" /><small>{chunk.translation}</small></span><span className="preview-chevron">›</span></button>)}</div></section>
  </div>;
}

function TranscriptPreview({ selectedId, onSelect }: { selectedId: string; onSelect: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => demoChunks.filter((chunk) => `${chunk.text} ${chunk.translation}`.toLowerCase().includes(query.toLowerCase())), [query]);
  return <section className="card card-pad preview-transcript-panel"><div className="row between preview-section-heading"><div><h2>Bilingual transcript</h2><p className="muted small">Click a row to play the matching audio range.</p></div><input className="input preview-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Japanese or Vietnamese" /></div><div className="preview-transcript-list">{filtered.map((chunk) => <button type="button" className={`preview-transcript-row ${chunk.id === selectedId ? "selected" : ""}`} key={chunk.id} onClick={() => onSelect(chunk.id)}><span className="preview-transcript-meta"><strong>{formatTime(chunk.start)}</strong><span className="speaker-dot" style={{ background: chunk.color }} />{chunk.speaker}</span><span><RubyText tokens={chunk.tokens} fallback={chunk.text} /><small>{chunk.translation}</small></span><span className="preview-play-glyph">▶</span></button>)}</div></section>;
}

function PracticePreview({ selected }: { selected: DemoChunk }) {
  const [mode, setMode] = useState<"full" | "cloze">("cloze");
  const [answer, setAnswer] = useState("");
  const [revealed, setRevealed] = useState(false);
  return <div className="preview-practice-grid"><section className="card card-pad preview-practice-main"><div className="row between"><div><span className="badge">Question 02 / 04</span><h2>Listen and reconstruct the sentence</h2></div><div className="tabs"><button className={mode === "full" ? "active" : ""} onClick={() => setMode("full")}>Full sentence</button><button className={mode === "cloze" ? "active" : ""} onClick={() => setMode("cloze")}>Fill blanks</button></div></div><div className="preview-practice-player"><button className="preview-big-play" onClick={() => setRevealed(false)}>▶</button><div><strong>Chunk 02 · {formatTime(selected.start)}–{formatTime(selected.end)}</strong><span className="muted small">Listen as many times as you need</span></div><button className="button small">Loop</button></div>{mode === "full" ? <textarea className="textarea preview-answer-input" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Type the whole Japanese sentence…" /> : <div className="preview-cloze"><span>はい、昨日</span><input className="input" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="fill the missing part" /><span>申し込みました。</span></div>}<div className="row wrap"><button className="button primary" onClick={() => setRevealed(true)}>Check answer</button><button className="button" onClick={() => setRevealed(true)}>Show answer</button><button className="button ghost">Mark difficult</button></div>{revealed ? <div className="preview-answer"><div className="row between"><strong>Answer</strong><span className="badge ready">AI unverified</span></div><RubyText tokens={selected.tokens} /><p>{selected.translation}</p><span className="muted small">Your answer is compared with Japanese normalization and character diff.</span></div> : <p className="muted small">The transcript, furigana and translation stay hidden until you check or reveal.</p>}</section><aside className="card card-pad preview-practice-side"><span className="muted small">SESSION SCORE</span><strong className="preview-score">86%</strong><div className="progress"><span style={{ width: "86%" }} /></div><div className="preview-stat-row"><span>Completed</span><strong>1 / 4</strong></div><div className="preview-stat-row"><span>Average</span><strong>86%</strong></div><div className="preview-stat-row"><span>Marked difficult</span><strong>2</strong></div><button className="button">Restart session</button></aside></div>;
}

function InsightsPreview() {
  return <div className="preview-stack"><section className="metric-grid"><div className="metric"><span className="muted small">SPEECH COVERAGE</span><strong>78.4%</strong><span className="muted small">24.9s of 31.8s</span></div><div className="metric"><span className="muted small">MEDIAN CHUNK</span><strong>7.2s</strong><span className="muted small">p95 · 8.4s</span></div><div className="metric"><span className="muted small">SPEAKERS</span><strong>2</strong><span className="muted small">Community-1 exclusive</span></div></section><section className="card card-pad preview-health"><div className="row between preview-section-heading"><div><h2>Pipeline health</h2><p className="muted small">Model and stage readiness for this project.</p></div><span className="badge ready">Ready to practice</span></div>{[["FFmpeg / FFprobe", "Ready", "#4ade80"], ["Silero VAD", "Completed", "#4ade80"], ["Community-1 diarization", "Completed", "#4ade80"], ["Audio8 ASR", "Completed", "#4ade80"], ["Gemma 4 translation", "Cached", "#60a5fa"]].map(([name, status, color]) => <div className="preview-health-row" key={name}><span className="preview-dot" style={{ background: color }} /> <strong>{name}</strong><span className="muted small">{status}</span></div>)}</section></div>;
}
