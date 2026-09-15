from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import StudioError
from jlpt_studio.db.models import (
    Chunk,
    ChunkText,
    MediaAsset,
    ModelRun,
    PipelineArtifact,
    ProcessingJob,
    Speaker,
)
from jlpt_studio.japanese import FuriganaService, normalize_japanese
from jlpt_studio.jobs.queue import check_cancelled, update_job_progress
from jlpt_studio.media.ffmpeg import FfmpegRunner
from jlpt_studio.media.waveform import generate_peaks
from jlpt_studio.pipeline.chunker import intersect_vad_and_diarization, semantic_chunk
from jlpt_studio.pipeline.diarization import CommunityDiarizationProvider
from jlpt_studio.pipeline.types import SegmentationConfig, SpeakerTurn, SpeechRegion
from jlpt_studio.pipeline.vad import SileroVadProvider
from jlpt_studio.providers.asr import Audio8AsrProvider
from jlpt_studio.services.audio_slices import cached_chunk_wav
from jlpt_studio.services.chunks import replace_project_chunks
from jlpt_studio.services.paths import (
    project_asset_dir,
    resolve_relative_project_path,
    to_relative_project_path,
)
from jlpt_studio.services.projects import get_project_or_404
from jlpt_studio.services.translation import translate_project_chunks

logger = logging.getLogger(__name__)

STAGE_PROGRESS = {
    "normalize": (3, 15),
    "waveform": (15, 20),
    "vad": (20, 32),
    "diarization": (32, 48),
    "chunking": (48, 58),
    "asr": (58, 78),
    "furigana": (78, 86),
    "translation": (86, 98),
}
SPEAKER_COLORS = ["#60a5fa", "#f472b6", "#34d399", "#fbbf24", "#a78bfa", "#fb7185"]


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JobCancelled(Exception):
    pass


class ProjectPipeline:
    def __init__(self, session: Session, settings: Settings, job: ProcessingJob) -> None:
        self.session = session
        self.settings = settings
        self.job = job
        self.project = get_project_or_404(session, job.project_id)
        self.ffmpeg = FfmpegRunner(settings)
        self.force = bool(job.payload_json.get("force", False))
        self.stages = list(
            job.payload_json.get(
                "stages", ["vad", "diarization", "chunking", "asr", "furigana", "translation"]
            )
        )
        self.segmentation_config = SegmentationConfig.from_preset(
            job.payload_json.get("segmentation_preset", "balanced")
        )
        overrides = {
            key: value
            for key, value in job.payload_json.items()
            if key in {
                "vad_threshold",
                "min_speech_ms",
                "min_silence_ms",
                "speech_pad_ms",
                "merge_gap_ms",
                "target_chunk_ms",
                "max_chunk_ms",
            }
            and value is not None
        }
        if overrides:
            self.segmentation_config = SegmentationConfig(
                **{**asdict(self.segmentation_config), **overrides}
            )
        self.num_speakers = job.payload_json.get("num_speakers")
        requested_chunk_ids = job.payload_json.get("chunk_ids")
        self.chunk_ids: set[str] | None = set(requested_chunk_ids) if requested_chunk_ids else None

    def _check_cancelled(self) -> None:
        if check_cancelled(self.session, self.job.id):
            raise JobCancelled

    def _progress(self, stage: str, fraction: float, message: str) -> None:
        start, end = STAGE_PROGRESS[stage]
        update_job_progress(
            self.session,
            self.job,
            stage=stage,
            progress=round(start + (end - start) * max(0.0, min(1.0, fraction))),
            message=message,
        )
        self._check_cancelled()

    def _source_asset(self) -> MediaAsset:
        asset = self.session.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == self.project.id, MediaAsset.kind == "source"
            )
        )
        if not asset:
            raise StudioError("SOURCE_MISSING", "Project chưa có audio nguồn", status_code=422)
        return asset

    def _upsert_asset(
        self,
        *,
        kind: str,
        path: Path,
        source: MediaAsset,
        duration_ms: int | None = None,
        sample_rate: int | None = None,
        channels: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MediaAsset:
        asset = self.session.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == self.project.id, MediaAsset.kind == kind
            )
        )
        if asset is None:
            asset = MediaAsset(project_id=self.project.id, kind=kind, relative_path="")
            self.session.add(asset)
        asset.relative_path = to_relative_project_path(self.settings, path)
        asset.original_name = path.name
        asset.size_bytes = path.stat().st_size if path.exists() else 0
        asset.duration_ms = duration_ms
        asset.sample_rate = sample_rate
        asset.channels = channels
        asset.sha256 = source.sha256
        asset.metadata_json = metadata or {}
        self.session.commit()
        return asset

    def _artifact(self, kind: str, input_hash: str) -> PipelineArtifact | None:
        return self.session.scalar(
            select(PipelineArtifact).where(
                PipelineArtifact.project_id == self.project.id,
                PipelineArtifact.kind == kind,
                PipelineArtifact.input_hash == input_hash,
            )
        )

    def _upsert_artifact(
        self, kind: str, input_hash: str, data: dict[str, Any]
    ) -> PipelineArtifact:
        existing = self._artifact(kind, input_hash)
        if existing:
            existing.data_json = data
            self.session.commit()
            return existing
        artifact = PipelineArtifact(
            project_id=self.project.id, kind=kind, input_hash=input_hash, data_json=data
        )
        self.session.add(artifact)
        self.session.commit()
        return artifact

    def _record_model_run(
        self,
        *,
        provider: str,
        model_id: str,
        start: float,
        input_hash: str | None,
        success: bool,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.session.add(
            ModelRun(
                project_id=self.project.id,
                job_id=self.job.id,
                provider=provider,
                model_id=model_id,
                model_revision=self.settings.audio8_revision if provider == "audio8" else None,
                config_json={"device": self.settings.device, "segmentation": asdict(self.segmentation_config)},
                input_hash=input_hash,
                output_json=output,
                duration_ms=round((time.monotonic() - start) * 1000),
                success=success,
                error=error,
            )
        )
        self.session.commit()

    def run(self) -> None:
        source = self._source_asset()
        if not source.sha256:
            raise StudioError(
                "SOURCE_HASH_MISSING", "Audio nguồn chưa có checksum", status_code=422
            )
        self._normalize(source)
        if "vad" in self.stages:
            self._run_vad(source)
        if "diarization" in self.stages:
            self._run_diarization(source)
        if "chunking" in self.stages:
            self._run_chunking(source)
        if "asr" in self.stages:
            self._run_asr(source)
        if "furigana" in self.stages:
            self._run_furigana(source)
        if "translation" in self.stages:
            self._run_translation(source)
        self.project.status = "ready"
        self.session.commit()

    def _normalize(self, source: MediaAsset) -> None:
        playback = self.session.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == self.project.id, MediaAsset.kind == "playback"
            )
        )
        analysis = self.session.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == self.project.id, MediaAsset.kind == "analysis"
            )
        )
        if playback and analysis and playback.relative_path and analysis.relative_path and not self.force:
            waveform = self.session.scalar(select(MediaAsset).where(MediaAsset.project_id == self.project.id, MediaAsset.kind == "waveform"))
            if waveform and Path(resolve_relative_project_path(self.settings, waveform.relative_path)).exists():
                return
        self._progress("normalize", 0.0, "Đang chuẩn hóa audio để phát và phân tích")
        source_path = resolve_relative_project_path(self.settings, source.relative_path)
        media_dir = project_asset_dir(self.settings, self.project.id, "normalized")
        playback_target = media_dir / "playback.opus"
        analysis_target = media_dir / "analysis.wav"
        playback_info, analysis_info = self.ffmpeg.normalize(
            source_path, playback_target, analysis_target
        )
        self._upsert_asset(
            kind="playback",
            path=playback_target,
            source=source,
            duration_ms=playback_info.duration_ms,
            sample_rate=playback_info.sample_rate,
            channels=playback_info.channels,
        )
        self._upsert_asset(
            kind="analysis",
            path=analysis_target,
            source=source,
            duration_ms=analysis_info.duration_ms,
            sample_rate=analysis_info.sample_rate,
            channels=analysis_info.channels,
        )
        self._progress("normalize", 1.0, "Đã chuẩn hóa audio")
        self._progress("waveform", 0.0, "Đang tạo waveform")
        waveform_path = (
            project_asset_dir(self.settings, self.project.id, "waveform") / "master.json"
        )
        generate_peaks(self.settings, analysis_target, waveform_path)
        self._upsert_asset(
            kind="waveform", path=waveform_path, source=source, metadata={"format": "peaks-v1"}
        )
        self._progress("waveform", 1.0, "Đã tạo waveform")

    def _analysis_path(self) -> Path:
        asset = self.session.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == self.project.id, MediaAsset.kind == "analysis"
            )
        )
        if not asset:
            raise StudioError(
                "ANALYSIS_ASSET_MISSING", "Không tìm thấy audio analysis", status_code=422
            )
        return resolve_relative_project_path(self.settings, asset.relative_path)

    def _run_vad(self, source: MediaAsset) -> PipelineArtifact:
        input_hash = _digest({"source": source.sha256, "config": asdict(self.segmentation_config)})
        existing = self._artifact("vad", input_hash)
        if existing and not self.force:
            return existing
        self._progress("vad", 0.0, "Đang phát hiện vùng có tiếng nói")
        start = time.monotonic()
        try:
            regions = SileroVadProvider().speech_regions(
                self._analysis_path(), self.segmentation_config
            )
            artifact = self._upsert_artifact(
                "vad",
                input_hash,
                {
                    "regions": [asdict(region) for region in regions],
                    "config": asdict(self.segmentation_config),
                },
            )
            self._record_model_run(
                provider="silero-vad",
                model_id="silero-vad",
                start=start,
                input_hash=input_hash,
                success=True,
                output={"region_count": len(regions)},
            )
        except Exception as error:
            self._record_model_run(
                provider="silero-vad",
                model_id="silero-vad",
                start=start,
                input_hash=input_hash,
                success=False,
                error=str(error),
            )
            raise
        self._progress("vad", 1.0, f"Đã tìm thấy {len(regions)} vùng có tiếng nói")
        return artifact

    def _run_diarization(self, source: MediaAsset) -> PipelineArtifact:
        input_hash = _digest(
            {
                "source": source.sha256,
                "num_speakers": self.num_speakers,
                "model": str(self.settings.pyannote_model_path or "community-1"),
            }
        )
        existing = self._artifact("diarization", input_hash)
        if existing and not self.force:
            return existing
        self._progress("diarization", 0.0, "Đang xác định người nói")
        start = time.monotonic()
        model_id = str(
            self.settings.pyannote_model_path or "pyannote/speaker-diarization-community-1"
        )
        try:
            turns = CommunityDiarizationProvider(self.settings).diarize(
                self._analysis_path(), num_speakers=self.num_speakers
            )
            artifact = self._upsert_artifact(
                "diarization",
                input_hash,
                {"turns": [asdict(turn) for turn in turns], "num_speakers": self.num_speakers},
            )
            self._record_model_run(
                provider="pyannote",
                model_id=model_id,
                start=start,
                input_hash=input_hash,
                success=True,
                output={"turn_count": len(turns)},
            )
        except Exception as error:
            self._record_model_run(
                provider="pyannote",
                model_id=model_id,
                start=start,
                input_hash=input_hash,
                success=False,
                error=str(error),
            )
            raise
        self._progress(
            "diarization",
            1.0,
            f"Đã xác định {len(set(turn.speaker_label for turn in turns))} người nói",
        )
        return artifact

    def _latest_artifact(self, kind: str) -> PipelineArtifact:
        artifact = self.session.scalar(
            select(PipelineArtifact)
            .where(PipelineArtifact.project_id == self.project.id, PipelineArtifact.kind == kind)
            .order_by(PipelineArtifact.updated_at.desc())
        )
        if not artifact:
            raise StudioError(
                "PIPELINE_PREREQUISITE_MISSING",
                f"Chưa có dữ liệu {kind}; hãy chạy stage trước.",
                status_code=422,
            )
        return artifact

    def _speaker_ids(self, labels: list[str]) -> dict[str, str]:
        existing = {
            speaker.label: speaker
            for speaker in self.session.scalars(
                select(Speaker).where(Speaker.project_id == self.project.id)
            ).all()
        }
        mapping: dict[str, str] = {}
        for index, label in enumerate(sorted(set(labels))):
            speaker = existing.get(label)
            if speaker is None:
                speaker = Speaker(
                    project_id=self.project.id,
                    label=label,
                    display_name=label.replace("SPEAKER_", "Speaker "),
                    color=SPEAKER_COLORS[index % len(SPEAKER_COLORS)],
                )
                self.session.add(speaker)
                self.session.flush()
            mapping[label] = speaker.id
        self.session.commit()
        return mapping

    def _run_chunking(self, source: MediaAsset) -> None:
        vad = self._latest_artifact("vad")
        diarization = self._latest_artifact("diarization")
        input_hash = _digest(
            {
                "vad": vad.input_hash,
                "diarization": diarization.input_hash,
                "config": asdict(self.segmentation_config),
            }
        )
        existing = self._artifact("chunks", input_hash)
        if existing and not self.force:
            return
        self._progress("chunking", 0.0, "Đang ghép vùng nói thành câu hội thoại")
        regions = [SpeechRegion(**item) for item in vad.data_json["regions"]]
        turns = [SpeakerTurn(**item) for item in diarization.data_json["turns"]]
        candidates = semantic_chunk(
            intersect_vad_and_diarization(regions, turns), self.segmentation_config
        )
        for candidate in candidates:
            if candidate.duration_ms > self.segmentation_config.hard_asr_cap_ms:
                raise StudioError(
                    "CHUNK_ASR_LIMIT_EXCEEDED",
                    "Có chunk vượt giới hạn ASR 28 giây; hãy chọn segmentation ngắn hơn.",
                    status_code=422,
                )
        mapping = self._speaker_ids([candidate.speaker_label for candidate in candidates])
        replace_project_chunks(
            self.session,
            self.project.id,
            [
                {
                    "start_ms": candidate.start_ms,
                    "end_ms": candidate.end_ms,
                    "speaker_label": candidate.speaker_label,
                    "vad_confidence": candidate.vad_confidence,
                    "diarization_confidence": candidate.diarization_confidence,
                }
                for candidate in candidates
            ],
            mapping,
            preserve_manual=not self.force,
        )
        self._upsert_artifact(
            "chunks",
            input_hash,
            {
                "chunk_count": len(candidates),
                "durations_ms": [candidate.duration_ms for candidate in candidates],
            },
        )
        self._progress("chunking", 1.0, f"Đã tạo {len(candidates)} chunk hội thoại")

    def _run_asr(self, source: MediaAsset) -> None:
        chunks = self.session.scalars(
            select(Chunk).where(Chunk.project_id == self.project.id).order_by(Chunk.order_index)
        ).all()
        if not chunks:
            raise StudioError("NO_CHUNKS", "Không có chunk để nhận dạng", status_code=422)
        pending = [
            chunk
            for chunk in chunks
            if self.chunk_ids is None or chunk.id in self.chunk_ids
            if self.force
            or (self.session.get(ChunkText, chunk.id) is None)
            or (self.session.get(ChunkText, chunk.id).reference_status in {"missing", "stale"})
        ]
        if not pending:
            return
        self._progress("asr", 0.0, "Đang nhận dạng tiếng Nhật bằng Audio8")
        paths = [
            cached_chunk_wav(
                self.session,
                self.settings,
                self.ffmpeg,
                project_id=self.project.id,
                start_ms=chunk.start_ms,
                end_ms=chunk.end_ms,
            )
            for chunk in pending
        ]
        start = time.monotonic()
        try:
            provider = Audio8AsrProvider(self.settings)
            texts = provider.transcribe_many(
                paths,
                on_progress=lambda current, total: self._progress(
                    "asr", current / total, f"Đang nhận dạng {current}/{total} audio chunk"
                ),
            )
            for chunk, raw_text in zip(pending, texts, strict=True):
                text = self.session.get(ChunkText, chunk.id) or ChunkText(chunk_id=chunk.id)
                text.asr_raw = raw_text
                text.asr_normalized = normalize_japanese(raw_text, forgiving=False)
                if text.reference_status != "user_confirmed":
                    text.reference_text = raw_text
                    text.reference_status = "ai_unverified"
                text.asr_input_hash = _digest(
                    {"source": source.sha256, "start": chunk.start_ms, "end": chunk.end_ms}
                )
                text.furigana_status = "stale"
                text.translation_status = "stale"
                self.session.add(text)
            self.session.commit()
            self._record_model_run(
                provider="audio8",
                model_id=self.settings.audio8_model_id,
                start=start,
                input_hash=source.sha256,
                success=True,
                output={"chunk_count": len(texts)},
            )
        except Exception as error:
            self._record_model_run(
                provider="audio8",
                model_id=self.settings.audio8_model_id,
                start=start,
                input_hash=source.sha256,
                success=False,
                error=str(error),
            )
            raise
        self._progress("asr", 1.0, "Đã nhận dạng transcript tiếng Nhật")

    def _run_furigana(self, source: MediaAsset) -> None:
        chunks = self.session.scalars(
            select(Chunk).where(Chunk.project_id == self.project.id).order_by(Chunk.order_index)
        ).all()
        pending: list[tuple[Chunk, ChunkText]] = []
        for chunk in chunks:
            text = self.session.get(ChunkText, chunk.id)
            if text and text.reference_text and (self.chunk_ids is None or chunk.id in self.chunk_ids) and (self.force or text.furigana_status != "ready"):
                pending.append((chunk, text))
        if not pending:
            return
        self._progress("furigana", 0.0, "Đang tạo furigana")
        service = FuriganaService()
        for index, (_, text) in enumerate(pending, start=1):
            text.furigana_json = service.tokenize(text.reference_text or "")
            text.furigana_status = "ready"
            text.furigana_input_hash = _digest(
                {"text": text.reference_text, "version": "sudachi-v1"}
            )
            self.session.commit()
            self._progress(
                "furigana", index / len(pending), f"Đang tạo furigana {index}/{len(pending)}"
            )
        self._progress("furigana", 1.0, "Đã tạo furigana")

    def _run_translation(self, source: MediaAsset) -> None:
        self._progress("translation", 0.0, "Đang dịch tiếng Việt theo ngữ cảnh")
        start = time.monotonic()
        try:
            count = translate_project_chunks(self.session, self.settings, self.project.id, chunk_ids=self.chunk_ids)
            self._record_model_run(
                provider="gemma-4",
                model_id=self.settings.llm_model,
                start=start,
                input_hash=source.sha256,
                success=True,
                output={"chunk_count": count},
            )
        except Exception as error:
            self._record_model_run(
                provider="gemma-4",
                model_id=self.settings.llm_model,
                start=start,
                input_hash=source.sha256,
                success=False,
                error=str(error),
            )
            raise
        self._progress("translation", 1.0, f"Đã dịch {count} chunk theo ngữ cảnh")
