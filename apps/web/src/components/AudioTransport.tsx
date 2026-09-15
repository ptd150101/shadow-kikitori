import { useAudio } from "./AudioProvider";
import { formatTime } from "../lib/format";

export default function AudioTransport() {
  const audio = useAudio();
  return <div className="card card-pad row wrap" style={{ position: "sticky", bottom: 12, zIndex: 5 }}>
    <button className="button" onClick={() => audio.skip(-2000)} aria-label="Lùi 2 giây">−2s</button>
    <button className="button primary" onClick={() => void audio.toggle()}>{audio.isPlaying ? "Tạm dừng" : "Phát"}</button>
    <button className="button" onClick={() => audio.skip(2000)} aria-label="Tiến 2 giây">+2s</button>
    <span className="muted small">{formatTime(audio.currentMs)} / {formatTime(audio.durationMs)}</span>
    <label className="row muted small">Âm lượng
      <input type="range" min="0" max="1" step="0.05" value={audio.volume} onChange={(event) => audio.setVolume(Number(event.target.value))} aria-label="Âm lượng" />
    </label>
    <label className="row muted small" style={{ marginLeft: "auto" }}>Tốc độ
      <select className="select" style={{ width: 82, padding: "6px 8px" }} value={audio.playbackRate} onChange={(event) => audio.setPlaybackRate(Number(event.target.value))}>
        {[0.5, 0.75, 1, 1.25, 1.5].map((rate) => <option key={rate} value={rate}>{rate}×</option>)}
      </select>
    </label>
  </div>;
}
