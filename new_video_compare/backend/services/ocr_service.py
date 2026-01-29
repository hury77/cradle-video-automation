"""
OCR Service for Text Detection and Comparison
Uses EasyOCR to extract text from video frames and compare between acceptance/emission
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Lazy load EasyOCR reader to avoid slow startup
_ocr_reader = None
_ocr_languages = None

def get_ocr_reader(languages: Optional[List[str]] = None):
    """
    Get or create EasyOCR reader (lazy loaded)
    
    Args:
        languages: List of language codes (e.g., ['en', 'pl']).
                   If None, uses default ['en'].
                   If changed from loaded model, re-initializes reader.
    """
    global _ocr_reader, _ocr_languages
    
    # Default to English if not provided
    if not languages:
        languages = ['en']
        
    # Always ensure 'en' is present (EasyOCR handles multilang well)
    if 'en' not in languages:
        languages.append('en')
        
    languages.sort() # Ensure consistent order for comparison
    
    # Check if we need to re-initialize
    if _ocr_reader is None or _ocr_languages != languages:
        import easyocr
        import gc
        
        # Cleanup old reader if exists
        if _ocr_reader is not None:
             logger.info(f"♻️ Reloading OCR Reader: {_ocr_languages} -> {languages}")
             del _ocr_reader
             gc.collect()
        else:
             logger.info(f"🔤 Initializing EasyOCR reader with languages: {languages}")
             
        _ocr_reader = easyocr.Reader(languages, gpu=False)
        _ocr_languages = languages
        logger.info("✅ EasyOCR reader initialized")
        
    return _ocr_reader


def extract_region(frame: np.ndarray, region: str) -> np.ndarray:
    """
    Extract specific region from frame for OCR
    
    Args:
        frame: Full video frame
        region: 'full_frame', 'bottom_fifth', 'bottom_third', 'none'
    
    Returns:
        Cropped frame region
    """
    if region == "full_frame" or region == "none":
        return frame
    
    height, width = frame.shape[:2]
    
    if region == "bottom_fifth":
        # Bottom 20% of frame - where disclaimers usually appear
        start_y = int(height * 0.8)
        return frame[start_y:height, 0:width]
    
    if region == "bottom_third":
        # Bottom 33% of frame
        start_y = int(height * 0.67)
        return frame[start_y:height, 0:width]
    
    if region == "bottom_half":
        # Bottom 50% of frame
        start_y = int(height * 0.5)
        return frame[start_y:height, 0:width]
    
    return frame


def extract_text_from_frame(
    frame: np.ndarray, 
    region: str = "bottom_fifth",
    languages: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Extract text from a video frame using OCR
    
    Args:
        frame: Video frame (numpy array in BGR format from cv2)
        region: Which region to OCR
        languages: Optional list of language codes
    
    Returns:
        List of detected text items with bounding boxes and confidence
    """
    try:
        reader = get_ocr_reader(languages)
        
        # Extract the specified region
        roi = extract_region(frame, region)
        
        # Convert BGR to RGB for EasyOCR
        if len(roi.shape) == 3 and roi.shape[2] == 3:
            roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        else:
            roi_rgb = roi
        
        # Run OCR
        results = reader.readtext(roi_rgb)
        
        # Format results
        text_items = []
        for (bbox, text, confidence) in results:
            if confidence > 0.3:  # Filter low confidence
                text_items.append({
                    "text": text.strip(),
                    "confidence": float(confidence),
                    "bbox": [[int(x), int(y)] for x, y in bbox]
                })
        
        return text_items
        
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return []


def extract_text_from_video(
    video_path: str,
    region: str = "bottom_fifth",
    sample_interval: float = 1.0,  # Sample every N seconds
    max_frames: int = 30,  # Max frames to analyze
    languages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Extract text from video by sampling frames at regular intervals
    
    Args:
        video_path: Path to video file
        region: Region to focus OCR on
        sample_interval: Seconds between sampled frames
        max_frames: Maximum number of frames to analyze
    
    Returns:
        Dict with all_text (unique texts), frame_texts (text per timestamp)
    """
    video_path = Path(video_path)
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return {"all_text": [], "frame_texts": [], "error": "File not found"}
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error(f"Failed to open video: {video_path}")
        return {"all_text": [], "frame_texts": [], "error": "Failed to open video"}
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    logger.info(f"🎬 OCR scanning video: {video_path.name} ({duration:.1f}s, {fps:.1f} fps)")
    
    frame_interval = int(fps * sample_interval)
    all_texts = set()
    frame_texts = []
    frames_analyzed = 0
    
    frame_idx = 0
    while frames_analyzed < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            break
        
        timestamp = frame_idx / fps
        
        # Run OCR on frame
        text_items = extract_text_from_frame(frame, region, languages=languages)
        
        if text_items:
            frame_data = {
                "timestamp": round(timestamp, 2),
                "frame_number": frame_idx,
                "texts": text_items
            }
            frame_texts.append(frame_data)
            
            for item in text_items:
                all_texts.add(item["text"])
        
        frames_analyzed += 1
        frame_idx += frame_interval
    
    cap.release()
    
    logger.info(f"✅ OCR complete: {frames_analyzed} frames, {len(all_texts)} unique texts found")
    
    return {
        "all_text": sorted(list(all_texts)),
        "frame_texts": frame_texts,
        "frames_analyzed": frames_analyzed,
        "region": region
    }



def compare_video_texts(
    acceptance_path: str,
    emission_path: str,
    region: str = "bottom_fifth",
    sample_interval: float = 0.5,
    languages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compare text content between acceptance and emission videos using strict temporal alignment.
    
    Args:
        acceptance_path: Path to acceptance video
        emission_path: Path to emission video
        region: OCR region focus
        sample_interval: Seconds between samples (default 0.5s for precision)
    
    Returns:
        Comparison results including differences found
    """
    logger.info("🔍 Starting OCR text comparison (Temporal Mode)...")
    
    # Extract text from both videos
    acceptance_ocr = extract_text_from_video(acceptance_path, region, sample_interval, languages=languages)
    emission_ocr = extract_text_from_video(emission_path, region, sample_interval, languages=languages)
    
    # Helper to map text -> list of (timestamp, confidence)
    def get_text_timestamps(ocr_result):
        text_map = {}
        for frame in ocr_result.get("frame_texts", []):
            ts = frame["timestamp"]
            for item in frame.get("texts", []):
                txt = item["text"]
                if txt not in text_map:
                    text_map[txt] = []
                text_map[txt].append((ts, item["confidence"]))
        return text_map

    acc_map = get_text_timestamps(acceptance_ocr)
    emm_map = get_text_timestamps(emission_ocr)
    
    differences = []
    tolerance = 0.5  # 500ms tolerance
    
    # 1. Check Missing in Emission (Present in Acc, missing in Emm at corresponding time)
    for text, occurrences in acc_map.items():
        emm_occurrences = emm_map.get(text, [])
        emm_timestamps = [t for t, _ in emm_occurrences]
        
        for ts_acc, conf_acc in occurrences:
            # Check if there is any timestamp in emm within tolerance
            match_found = False
            for ts_emm in emm_timestamps:
                if abs(ts_acc - ts_emm) <= tolerance:
                    match_found = True
                    break
            
            if not match_found:
                differences.append({
                    "type": "missing_in_emission",
                    "text": text,
                    "timestamp": ts_acc,
                    "source": "acceptance",
                    "confidence": conf_acc
                })

    # 2. Check Extra in Emission (Present in Emm, missing in Acc at corresponding time)
    for text, occurrences in emm_map.items():
        acc_occurrences = acc_map.get(text, [])
        acc_timestamps = [t for t, _ in acc_occurrences]
        
        for ts_emm, conf_emm in occurrences:
            # Check if there is any timestamp in acc within tolerance
            match_found = False
            for ts_acc in acc_timestamps:
                if abs(ts_emm - ts_acc) <= tolerance:
                    match_found = True
                    break
            
            if not match_found:
                differences.append({
                    "type": "extra_in_emission",
                    "text": text,
                    "timestamp": ts_emm,
                    "source": "emission",
                    "confidence": conf_emm
                })
    
    # Sort differences by timestamp
    differences.sort(key=lambda x: x["timestamp"])
    
    # Global stats for summary (Set based)
    acceptance_texts = set(acc_map.keys())
    emission_texts = set(emm_map.keys())
    common_texts = acceptance_texts & emission_texts
    only_in_acceptance = acceptance_texts - emission_texts
    only_in_emission = emission_texts - acceptance_texts

    # Calculate similarity score based on temporal matches vs total items detected
    # Total unique instances = sum of all occurrences in both lists
    acc_total_count = sum(len(v) for v in acc_map.values())
    emm_total_count = sum(len(v) for v in emm_map.values())
    total_instances = acc_total_count + emm_total_count
    total_diffs = len(differences)
    
    if total_instances > 0:
        # Simple similarity: (Total - Diffs) / Total. 
        # Note: A difference typically counts as 1 mismatch. 
        # If perfect match: 0 diffs -> 1.0
        text_similarity = max(0.0, (total_instances - total_diffs) / total_instances)
    else:
        text_similarity = 1.0
    
    result = {
        "text_similarity": round(text_similarity, 3),
        "acceptance_text_count": len(acceptance_texts),
        "emission_text_count": len(emission_texts),
        "common_texts": sorted(list(common_texts)),
        "only_in_acceptance": sorted(list(only_in_acceptance)), # Retain for legacy View
        "only_in_emission": sorted(list(only_in_emission)),     # Retain for legacy View
        "differences": differences,
        "has_text_differences": len(differences) > 0,
        "region_analyzed": region,
        "acceptance_frames": acceptance_ocr.get("frames_analyzed", 0),
        "emission_frames": emission_ocr.get("frames_analyzed", 0)
    }
    
    if len(differences) > 0:
        logger.warning(f"⚠️ Found {len(differences)} temporal text differences!")
    else:
        logger.info("✅ No temporal text differences found")
    
    return result
