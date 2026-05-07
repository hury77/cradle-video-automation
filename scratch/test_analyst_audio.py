import sys
from pathlib import Path
sys.path.append(str(Path("new_video_compare/backend").absolute()))

from services.analyst_service import AnalystService

analyst = AnalystService()

metrics = {
  "audio_similarity": 0.0,
  "audio_analysis_data": {
    "similarity": {"error": "FFmpeg failed: blah blah"},
    "speech_to_text": {
      "comparison": {"word_count_a": 0}
    }
  }
}

analyst._last_metrics = metrics

sample_response = '{"verdict": "approve", "reasoning": "Pełna zgodność audio i wideo. Transkrypcja idealna."}'

result = analyst._parse_response(sample_response)
print("Resulting reasoning:", result['reasoning'])

