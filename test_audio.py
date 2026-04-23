import asyncio
from new_video_compare.backend.services.audio_service import transcribe_single_file
import logging

logging.basicConfig(level=logging.INFO)

file_path = "new_video_compare/backend/uploads/119931_981113_SPOTICAR_Fruhlingswoche_TV_Spots_20s_DEE_845a00V_f8ccc83e.mp4"
result = transcribe_single_file(file_path, language="de", model_name="small", use_source_separation=True)
print(result)
