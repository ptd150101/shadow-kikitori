from __future__ import annotations

from jlpt_studio.pipeline.types import ChunkCandidate, SegmentationConfig, SpeakerTurn, SpeechRegion


def intersect_vad_and_diarization(
    regions: list[SpeechRegion], turns: list[SpeakerTurn]
) -> list[ChunkCandidate]:
    """Intersect speech with exclusive speaker turns.

    Unlabelled VAD islands are retained as SPEAKER_00 instead of silently losing
    real audio when diarization has low confidence.
    """
    if not regions:
        return []
    if not turns:
        return [
            ChunkCandidate(region.start_ms, region.end_ms, "SPEAKER_00", region.confidence)
            for region in regions
        ]
    results: list[ChunkCandidate] = []
    for region in regions:
        overlaps: list[tuple[int, int, SpeakerTurn]] = []
        for turn in turns:
            start = max(region.start_ms, turn.start_ms)
            end = min(region.end_ms, turn.end_ms)
            if end - start >= 50:
                overlaps.append((start, end, turn))
        if not overlaps:
            nearest = min(
                turns,
                key=lambda turn: min(
                    abs(turn.start_ms - region.end_ms), abs(region.start_ms - turn.end_ms)
                ),
            )
            results.append(
                ChunkCandidate(
                    region.start_ms,
                    region.end_ms,
                    nearest.speaker_label,
                    region.confidence,
                    nearest.confidence,
                )
            )
            continue
        for start, end, turn in overlaps:
            results.append(
                ChunkCandidate(start, end, turn.speaker_label, region.confidence, turn.confidence)
            )
    return _coalesce_adjacent(results, gap_ms=50)


def _coalesce_adjacent(items: list[ChunkCandidate], gap_ms: int, max_duration_ms: int | None = None) -> list[ChunkCandidate]:
    if not items:
        return []
    items = sorted(items, key=lambda item: (item.start_ms, item.end_ms))
    merged: list[ChunkCandidate] = [items[0]]
    for item in items[1:]:
        previous = merged[-1]
        if (
            item.speaker_label == previous.speaker_label
            and item.start_ms - previous.end_ms <= gap_ms
            and (max_duration_ms is None or item.end_ms - previous.start_ms <= max_duration_ms)
        ):
            merged[-1] = ChunkCandidate(
                previous.start_ms,
                max(previous.end_ms, item.end_ms),
                previous.speaker_label,
                previous.vad_confidence,
                previous.diarization_confidence,
            )
        else:
            merged.append(item)
    return merged


def semantic_chunk(items: list[ChunkCandidate], config: SegmentationConfig) -> list[ChunkCandidate]:
    """Merge short voice islands into coherent utterance-sized chunks.

    Speaker changes are hard boundaries. Pauses are preserved within a chunk but
    are the preferred split points for long utterances.
    """
    if not items:
        return []
    items = sorted(items, key=lambda item: (item.start_ms, item.end_ms))
    groups: list[list[ChunkCandidate]] = []
    current: list[ChunkCandidate] = [items[0]]
    for item in items[1:]:
        first = current[0]
        previous = current[-1]
        proposed_duration = item.end_ms - first.start_ms
        same_speaker = item.speaker_label == previous.speaker_label
        close_enough = item.start_ms - previous.end_ms <= config.merge_gap_ms
        under_hard_cap = proposed_duration <= config.hard_asr_cap_ms
        if same_speaker and close_enough and under_hard_cap:
            current.append(item)
        else:
            groups.append(current)
            current = [item]
    groups.append(current)

    output: list[ChunkCandidate] = []
    for group in groups:
        output.extend(_split_group_at_pauses(group, config))
    output = _merge_micro_chunks(output, config)
    return _coalesce_adjacent(output, gap_ms=0, max_duration_ms=config.hard_asr_cap_ms)


def _split_group_at_pauses(
    group: list[ChunkCandidate], config: SegmentationConfig
) -> list[ChunkCandidate]:
    if not group:
        return []
    result: list[ChunkCandidate] = []
    start_index = 0
    while start_index < len(group):
        first = group[start_index]
        # A VAD island can be longer than Audio8's context. Split that island at
        # an exact millisecond boundary while retaining the speaker label.
        if first.duration_ms > config.hard_asr_cap_ms:
            cursor = first.start_ms
            while cursor < first.end_ms:
                end = min(first.end_ms, cursor + config.hard_asr_cap_ms)
                result.append(ChunkCandidate(cursor, end, first.speaker_label, first.vad_confidence, first.diarization_confidence))
                cursor = end
            start_index += 1
            continue
        chosen_end = start_index
        best_end = start_index
        for index in range(start_index, len(group)):
            duration = group[index].end_ms - first.start_ms
            if duration <= config.target_chunk_ms:
                best_end = index
            if duration > config.max_chunk_ms or duration > config.hard_asr_cap_ms:
                break
            chosen_end = index
        if best_end > start_index and (chosen_end < len(group) - 1 or best_end == len(group) - 1):
            chosen_end = best_end
        selected = group[start_index : chosen_end + 1]
        result.append(ChunkCandidate(selected[0].start_ms, selected[-1].end_ms, selected[0].speaker_label, selected[0].vad_confidence, selected[0].diarization_confidence))
        start_index = chosen_end + 1
    return result


def _merge_micro_chunks(
    items: list[ChunkCandidate], config: SegmentationConfig
) -> list[ChunkCandidate]:
    if len(items) < 2:
        return items
    pending = list(items)
    changed = True
    while changed:
        changed = False
        for index, item in enumerate(list(pending)):
            if item.duration_ms >= config.min_chunk_ms:
                continue
            candidates: list[tuple[int, int]] = []
            if index > 0 and pending[index - 1].speaker_label == item.speaker_label:
                candidates.append((index - 1, item.start_ms - pending[index - 1].end_ms))
            if index + 1 < len(pending) and pending[index + 1].speaker_label == item.speaker_label:
                candidates.append((index + 1, pending[index + 1].start_ms - item.end_ms))
            candidates = [
                candidate
                for candidate in candidates
                if candidate[1] <= config.merge_gap_ms * 2
                and pending[min(candidate[0], index)].start_ms
                <= pending[max(candidate[0], index)].end_ms
                and pending[max(candidate[0], index)].end_ms
                - pending[min(candidate[0], index)].start_ms
                <= config.hard_asr_cap_ms
            ]
            if not candidates:
                continue
            neighbor_index = min(candidates, key=lambda candidate: candidate[1])[0]
            left_index, right_index = sorted((index, neighbor_index))
            left, right = pending[left_index], pending[right_index]
            merged = ChunkCandidate(
                left.start_ms,
                right.end_ms,
                left.speaker_label,
                left.vad_confidence,
                left.diarization_confidence,
            )
            pending[left_index : right_index + 1] = [merged]
            changed = True
            break
    return pending
