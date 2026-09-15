# Data model

The SQLite schema is intentionally revisioned with Alembic. `projects.active_revision` is the optimistic concurrency token for timeline operations; every boundary, speaker and ordering mutation increments it. `chunks.boundary_revision` protects a single row from stale browser edits.

| Table | Purpose |
| --- | --- |
| `projects` | Project title, source URL/type, status and active revision |
| `media_assets` | Source, normalized playback/analysis and waveform metadata |
| `pipeline_artifacts` | Hash-addressed VAD, diarization and chunking results |
| `processing_jobs` | Durable queue state, heartbeat, retry and error details |
| `speakers` | Community-1 labels plus user display name/color |
| `chunks` | Ordered timeline regions, speaker and confidence values |
| `chunk_texts` | ASR, confirmed reference, furigana and Vietnamese translation |
| `model_runs` | Provider/model revision, config, duration, VRAM and outcome |
| `exercises` / `attempts` | Full/cloze practice, scores, diff and difficulty flag |
| `translation_cache` | Context-sensitive Gemma batch cache |
| `app_settings` | Runtime overrides without exposing the HF token |

`reference_status` is one of `missing`, `ai_unverified`, `user_confirmed` or `stale`. Geometry edits invalidate furigana, translation and exercises while preserving a user-confirmed reference for review.
