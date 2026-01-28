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

def get_ocr_reader():
    """Get or create EasyOCR reader (lazy loaded)"""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        logger.info("🔤 Initializing EasyOCR reader...")
        _ocr_reader = easyocr.Reader(['pl', 'en'], gpu=False)  # Polish + English
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
    region: str = "bottom_fifth"
) -> List[Dict[str, Any]]:
    """
    Extract text from a video frame using OCR
    
    Args:
        frame: Video frame (numpy array in BGR format from cv2)
        region: Which region to OCR
    
    Returns:
        List of detected text items with bounding boxes and confidence
    """
    try:
        reader = get_ocr_reader()
        
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
    max_frames: int = 30  # Max frames to analyze
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
        text_items = extract_text_from_frame(frame, region)
        
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
    sample_interval: float = 1.0
) -> Dict[str, Any]:
    """
    Compare text content between acceptance and emission videos
    
    Args:
        acceptance_path: Path to acceptance video
        emission_path: Path to emission video
        region: OCR region focus
        sample_interval: Seconds between samples
    
    Returns:
        Comparison results including differences found
    """
    logger.info("🔍 Starting OCR text comparison...")
    
    # Extract text from both videos
    acceptance_ocr = extract_text_from_video(acceptance_path, region, sample_interval)
    emission_ocr = extract_text_from_video(emission_path, region, sample_interval)
    
    acceptance_texts = set(acceptance_ocr.get("all_text", []))
    emission_texts = set(emission_ocr.get("all_text", []))
    
    # Find differences
    only_in_acceptance = acceptance_texts - emission_texts
    only_in_emission = emission_texts - acceptance_texts
    common_texts = acceptance_texts & emission_texts
    
    # Calculate similarity
    total_unique = len(acceptance_texts | emission_texts)
    if total_unique > 0:
        text_similarity = len(common_texts) / total_unique
    else:
        text_similarity = 1.0  # No text in either = identical
    
    # Build detailed differences with timestamps
    differences = []
    
    for text in only_in_acceptance:
        # Find timestamp where this text appears
        for frame_data in acceptance_ocr.get("frame_texts", []):
            for item in frame_data.get("texts", []):
                if item["text"] == text:
                    differences.append({
                        "type": "missing_in_emission",
                        "text": text,
                        "timestamp": frame_data["timestamp"],
                        "source": "acceptance",
                        "confidence": item["confidence"]
                    })
                    break
    
    for text in only_in_emission:
        for frame_data in emission_ocr.get("frame_texts", []):
            for item in frame_data.get("texts", []):
                if item["text"] == text:
                    differences.append({
                        "type": "extra_in_emission",
                        "text": text,
                        "timestamp": frame_data["timestamp"],
                        "source": "emission",
                        "confidence": item["confidence"]
                    })
                    break
    
    result = {
        "text_similarity": round(text_similarity, 3),
        "acceptance_text_count": len(acceptance_texts),
        "emission_text_count": len(emission_texts),
        "common_texts": list(common_texts),
        "only_in_acceptance": list(only_in_acceptance),
        "only_in_emission": list(only_in_emission),
        "differences": differences,
        "has_text_differences": len(differences) > 0,
        "region_analyzed": region,
        "acceptance_frames": acceptance_ocr.get("frames_analyzed", 0),
        "emission_frames": emission_ocr.get("frames_analyzed", 0)
    }
    
    if len(differences) > 0:
        logger.warning(f"⚠️ Found {len(differences)} text differences!")
    else:
        logger.info("✅ No text differences found")
    
    return result
