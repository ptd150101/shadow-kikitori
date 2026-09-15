from __future__ import annotations

import array
import json
import math
import subprocess
from pathlib import Path

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import StudioError


def generate_peaks(
    settings: Settings, source: Path, target: Path, *, points: int = 4000
) -> dict[str, object]:
    """Create compact min/max waveform peaks without loading the entire audio in the browser."""
    command = [
        settings.ffmpeg_path,
        "-v",
        "error",
        "-i",
        str(source),
        "-f",
        "s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, timeout=60 * 30)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
        raise StudioError("WAVEFORM_FAILED", "Không thể tạo waveform", status_code=422) from error
    samples = array.array("h")
    samples.frombytes(result.stdout)
    if not samples:
        data: dict[str, object] = {"sample_rate": 16000, "duration_ms": 0, "peaks": []}
    else:
        bucket_size = max(1, math.ceil(len(samples) / points))
        peaks: list[list[float]] = []
        for start in range(0, len(samples), bucket_size):
            bucket = samples[start : start + bucket_size]
            peaks.append([round(min(bucket) / 32768, 5), round(max(bucket) / 32768, 5)])
        data = {
            "sample_rate": 16000,
            "duration_ms": round(len(samples) / 16),
            "points": len(peaks),
            "peaks": peaks,
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    temp.replace(target)
    return data
