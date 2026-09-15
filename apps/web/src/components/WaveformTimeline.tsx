import { useMemo, useRef, useState } from "react";
import type { Chunk, Waveform } from "../types/api";
import { classNames } from "../lib/format";

type DragState = { chunkId: string; edge: "start" | "end" } | null;

export default function WaveformTimeline({
  waveform,
  chunks,
  selectedChunkId,
  currentMs,
  onSelectChunk,
  onSeek,
  onPreviewBoundary,
  onCommitBoundary,
}: {
  waveform: Waveform;
  chunks: Chunk[];
  selectedChunkId: string | null;
  currentMs: number;
  onSelectChunk: (id: string) => void;
  onSeek: (milliseconds: number) => void;
  onPreviewBoundary: (id: string, values: Partial<Pick<Chunk, "start_ms" | "end_ms">>) => void;
  onCommitBoundary: (id: string) => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<DragState>(null);
  const [zoom, setZoom] = useState(1);
  const maxBars = Math.round(600 * zoom);
  const bars = useMemo(() => {
    const stride = Math.max(1, Math.ceil(waveform.peaks.length / maxBars));
    return waveform.peaks.filter((_, index) => index % stride === 0);
  }, [waveform.peaks, maxBars]);
  const duration = waveform.duration_ms || 1;

  function toMs(clientX: number) {
    const rect = rootRef.current?.getBoundingClientRect();
    if (!rect) return 0;
    return Math.round(Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)) * duration);
  }

  function boundsFor(chunk: Chunk) {
    const index = chunks.findIndex((item) => item.id === chunk.id);
    return {
      min: index > 0 ? chunks[index - 1].end_ms : 0,
      max: index < chunks.length - 1 ? chunks[index + 1].start_ms : duration,
    };
  }

  function pointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag) return;
    const chunk = chunks.find((item) => item.id === drag.chunkId);
    if (!chunk) return;
    const candidate = toMs(event.clientX);
    const bounds = boundsFor(chunk);
    if (drag.edge === "start") {
      onPreviewBoundary(chunk.id, { start_ms: Math.min(chunk.end_ms - 250, Math.max(bounds.min, candidate)) });
    } else {
      onPreviewBoundary(chunk.id, { end_ms: Math.max(chunk.start_ms + 250, Math.min(bounds.max, candidate)) });
    }
  }

  return <div className="timeline-wrap"><div
    ref={rootRef}
    className="timeline"
    onPointerMove={pointerMove}
    onPointerUp={() => { if (drag) onCommitBoundary(drag.chunkId); setDrag(null); }}
    onPointerLeave={() => { if (drag) onCommitBoundary(drag.chunkId); setDrag(null); }}
    onPointerDown={(event) => {
      if (event.target === event.currentTarget) onSeek(toMs(event.clientX));
    }}
  >
    <svg className="timeline-wave" preserveAspectRatio="none" viewBox={`0 0 ${bars.length} 100`} aria-label="Waveform">
      {bars.map(([min, max], index) => <line key={index} x1={index + .5} x2={index + .5} y1={(1 - max) * 50} y2={(1 - min) * 50} />)}
    </svg>
    {chunks.map((chunk) => {
      const left = (chunk.start_ms / duration) * 100;
      const width = ((chunk.end_ms - chunk.start_ms) / duration) * 100;
      return <div
        key={chunk.id}
        className={classNames("timeline-region", selectedChunkId === chunk.id && "selected")}
        style={{ left: `${left}%`, width: `${Math.max(width, .3)}%`, borderColor: chunk.speaker?.color, backgroundColor: `${chunk.speaker?.color ?? "#60a5fa"}33` }}
        onPointerDown={(event) => { event.stopPropagation(); onSelectChunk(chunk.id); onSeek(chunk.start_ms); }}
      >
        {selectedChunkId === chunk.id ? <>
          <span className="timeline-edge start" onPointerDown={(event) => { event.stopPropagation(); event.currentTarget.setPointerCapture(event.pointerId); setDrag({ chunkId: chunk.id, edge: "start" }); }} />
          <span className="timeline-edge end" onPointerDown={(event) => { event.stopPropagation(); event.currentTarget.setPointerCapture(event.pointerId); setDrag({ chunkId: chunk.id, edge: "end" }); }} />
        </> : null}
      </div>;
    })}
    <span className="timeline-playhead" style={{ left: `${Math.min(100, (currentMs / duration) * 100)}%` }} />
  </div><div className="row timeline-controls"><span className="muted small">Zoom</span><input type="range" min="1" max="6" step="1" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} aria-label="Zoom waveform" /><span className="muted small">{zoom}×</span></div></div>;
}
