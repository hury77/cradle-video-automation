# Implementation Plan - Fix STT Skipping on Loudness Mismatch

Ensure that the Speech-to-Text (Whisper) pipeline runs whenever significant loudness differences (LUFS/Peak) are detected, regardless of the spectral similarity score.

## User Review Required

> [!IMPORTANT]
> This change will increase processing time and memory usage for jobs that have loudness differences but high spectral similarity, as they will no longer benefit from the "Fast Path" optimization.

## Proposed Changes

### Audio Service

#### [MODIFY] [audio_service.py](file:///Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/services/audio_service.py)
- Update `compare_spoken_text` signature to include `force_stt: bool = False`.
- Update the "Fast Path" condition to only trigger if `force_stt` is `False`.

### Comparison Service

#### [MODIFY] [comparison_service.py](file:///Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/services/comparison_service.py)
- Pass `has_loudness_differences` from the loudness result as `force_stt` to `compare_spoken_text`.

## Verification Plan

### Automated Tests
- I will create a reproduction script that mocks the loudness difference and high similarity to verify that `compare_spoken_text` no longer skips.

### Manual Verification
- Run a re-analysis of Job 341 (if possible) or a similar test case to ensure Whisper is now triggered.
