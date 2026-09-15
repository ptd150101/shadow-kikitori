"""Small benchmark helper; run after installing the AI group and supplying WAV files."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from jlpt_studio.core.config import get_settings
from jlpt_studio.providers.asr.audio8 import Audio8AsrProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", nargs="+", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    results = Audio8AsrProvider(get_settings()).transcribe_many(args.wav)
    elapsed = time.perf_counter() - started
    for path, result in zip(args.wav, results, strict=True):
        print(f"{path}: {result}")
    print(f"files={len(results)} elapsed_s={elapsed:.2f} rtf={elapsed / max(len(results), 1):.2f}")


if __name__ == "__main__":
    main()
