
# Problem Report: Mixed Language Audio & Missing VO

## Symptoms
1. **Source:** Video with English song (singing) at start, Portuguese VO at end.
2. **Current Result:**
    - Detected Language: Portuguese.
    - English Song: Transcribed with errors (likely forced into PT context).
    - Portuguese VO: **Not detected at all** (Silence?).
3. **Suspected Causes:**
    - **Whisper Language Lock:** Whisper decoder is conditioned on the first detected language. If it thinks it's PT, it tries to decode English audio as PT words.
    - **Demucs Separation:** The song might be classified as "music" and removed from the "vocals" track, leaving only the VO. If the VO is short or quiet, it might be missed.
    - **VAD (Voice Activity Detection):** If the VO is at the very end, it might be cut off or below threshold.

## Proposed Strategy

### 1. Demucs Verification
- Check if the "vocals" track from Demucs actually contains the song lyrics.
- If Demucs removes the song (thinking it's background music), we might need to use the **original audio** for transcription in certain modes, or mix "vocals" + "bass/drums/other" if we want lyrics.
- **Action:** Test Demucs behavior on mixed content.

### 2. Whisper Multilingual Config
- Ensure `task="transcribe"` is set (not `translate`).
- **Critical:** Whisper by default (in Python API) detects language from the *first 30 seconds*. If the song is English and VO is Portuguese, it might get confused.
- **Solution:** Enable `language=None` (Auto) but check if we can force segment-level detection or split audio into chunks.
- **Alternative:** Use `beam_size=5` and `best_of=5` to improve accuracy.

### 3. Missing VO at End
- Could be a **trimming issue**.
- Check `audio_service.py` for any "silence removal" or shortening of audio clips.
- Check `video_processor.py` or wherever audio is extracted - maybe it cuts off too early?
