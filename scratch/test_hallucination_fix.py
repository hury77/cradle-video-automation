import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "new_video_compare/backend"))

from services.audio_service import _detect_and_strip_loop_hallucination

def test():
    print("--- TESTING HALLUCINATION DETECTOR ---")
    
    # CASE 1: Job 321 Syllable Loop (Hyphenated)
    garbage_text = "DitLIte-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te-te"
    result = _detect_and_strip_loop_hallucination(garbage_text)
    print(f"CASE 1 (Hyphens): Result length = {len(result)}")
    if not result:
        print("✅ Correctly stripped hyphenated syllable loop.")
    else:
        print("❌ FAILED to strip hyphenated loop.")

    # CASE 2: Non-hyphenated syllable loop (e.g. tetetete)
    garbage_text_2 = "Sometext tetetetetetetetetetetetetetetete moretext"
    result = _detect_and_strip_loop_hallucination(garbage_text_2)
    print(f"\nCASE 2 (Dense): Result length = {len(result)}")
    if not result:
        print("✅ Correctly stripped dense syllable loop.")
    else:
        print("❌ FAILED to strip dense loop.")

    # CASE 3: Single-word loop
    garbage_text_3 = "word word word word word word word word word word word word"
    result = _detect_and_strip_loop_hallucination(garbage_text_3)
    print(f"\nCASE 3 (Single word): Result length = {len(result)}")
    if not result:
        print("✅ Correctly stripped single-word loop.")
    else:
        print("❌ FAILED to strip single-word loop.")

    # CASE 4: Normal text (should NOT be stripped)
    normal_text = "This is a normal Dutch text about Peugeot cars in the Netherlands."
    result = _detect_and_strip_loop_hallucination(normal_text)
    print(f"\nCASE 4 (Normal): Result = '{result}'")
    if result == normal_text:
        print("✅ Correctly preserved normal text.")
    else:
        print("❌ UNEXPECTEDLY stripped normal text.")

if __name__ == "__main__":
    test()
