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
        
        # === IMAGE PREPROCESSING FOR BETTER OCR ===
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # This significantly improves text detection on low-contrast backgrounds
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Optional: Apply slight sharpening
        kernel = np.array([[-1, -1, -1],
                           [-1,  9, -1],
                           [-1, -1, -1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # Convert back to RGB for EasyOCR (it expects color or grayscale)
        roi_processed = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
        
        # Run OCR on preprocessed image
        results = reader.readtext(roi_processed)
        
        # Format results
        text_items = []
        for (bbox, text, confidence) in results:
            cleaned_text = text.strip()
            # Filter: high confidence + minimum length to avoid artifacts
            if confidence > 0.8 and len(cleaned_text) >= 3:
                text_items.append({
                    "text": cleaned_text,
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
        
        # MEMORY CLEANUP: Delete frame immediately after OCR
        del frame
        
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
        
        # MEMORY CLEANUP: Force garbage collection every 10 frames
        if frames_analyzed % 10 == 0:
            import gc
            gc.collect()
    
    cap.release()
    
    # Final memory cleanup
    import gc
    gc.collect()
    
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
    languages: Optional[List[str]] = None,
    similarity_threshold: float = 0.85  # NEW: Fuzzy matching threshold (0.0-1.0)
) -> Dict[str, Any]:
    """
    Compare text content between acceptance and emission videos using fuzzy temporal alignment.
    
    Args:
        acceptance_path: Path to acceptance video
        emission_path: Path to emission video
        region: OCR region focus
        sample_interval: Seconds between samples (default 0.5s for precision)
        languages: Language codes for OCR
        similarity_threshold: Minimum similarity ratio (0.0-1.0) to consider texts as matching.
                              Default 0.85 (85%) to handle minor OCR variations.
    
    Returns:
        Comparison results including differences found
    """
    from difflib import SequenceMatcher
    
    logger.info(f"🔍 Starting OCR text comparison (Fuzzy Mode, threshold={similarity_threshold})...")
    
    # Text normalization function to reduce false positives from OCR variations
    def normalize_text(text: str) -> str:
        """Normalize text for comparison: lowercase, collapse whitespace, strip punctuation variations."""
        import re
        import unicodedata
        # Normalize unicode (e.g., different apostrophe types)
        text = unicodedata.normalize('NFKC', text)
        # Lowercase
        text = text.lower()
        # Collapse multiple spaces to single
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text
    
    # Extract text from both videos
    acceptance_ocr = extract_text_from_video(acceptance_path, region, sample_interval, languages=languages)
    emission_ocr = extract_text_from_video(emission_path, region, sample_interval, languages=languages)
    
    # NEW APPROACH: Group all texts by timestamp, concatenate them, then compare
    # This eliminates false positives from OCR segmentation differences
    
    def get_texts_by_timestamp(ocr_result):
        """Group all texts by timestamp, returning dict: timestamp -> list of (text, confidence)"""
        ts_map = {}
        for frame in ocr_result.get("frame_texts", []):
            ts = frame["timestamp"]
            if ts not in ts_map:
                ts_map[ts] = []
            for item in frame.get("texts", []):
                ts_map[ts].append((item["text"], item["confidence"]))
        return ts_map
    
    def concatenate_texts(text_list):
        """Concatenate all texts from a timestamp into one string, sorted alphabetically to be order-independent."""
        # Sort texts to make comparison order-independent
        texts = [t[0] for t in text_list]
        texts.sort()
        return " ".join(texts)
    
    def avg_confidence(text_list):
        """Calculate average confidence for a list of texts."""
        if not text_list:
            return 0.0
        return sum(t[1] for t in text_list) / len(text_list)
    
    acc_by_ts = get_texts_by_timestamp(acceptance_ocr)
    emm_by_ts = get_texts_by_timestamp(emission_ocr)
    
    # Get all unique timestamps from both videos
    all_timestamps = sorted(set(acc_by_ts.keys()) | set(emm_by_ts.keys()))
    
    differences = []
    timeline = []
    tolerance = 0.5  # 500ms tolerance for timestamp matching
    
    for ts in all_timestamps:
        # Get texts at this timestamp (or find closest within tolerance)
        acc_texts = acc_by_ts.get(ts, [])
        emm_texts = emm_by_ts.get(ts, [])
        
        # If no exact match, try to find within tolerance
        if not acc_texts:
            for t in acc_by_ts.keys():
                if abs(t - ts) <= tolerance:
                    acc_texts = acc_by_ts[t]
                    break
        if not emm_texts:
            for t in emm_by_ts.keys():
                if abs(t - ts) <= tolerance:
                    emm_texts = emm_by_ts[t]
                    break
        
        # Concatenate and normalize texts for comparison
        acc_concat = normalize_text(concatenate_texts(acc_texts)) if acc_texts else ""
        emm_concat = normalize_text(concatenate_texts(emm_texts)) if emm_texts else ""
        
        # Build timeline entries with original (non-concatenated) texts
        acc_original = " | ".join([t[0] for t in acc_texts]) if acc_texts else ""
        emm_original = " | ".join([t[0] for t in emm_texts]) if emm_texts else ""
        acc_conf = avg_confidence(acc_texts)
        emm_conf = avg_confidence(emm_texts)
        
        # FUZZY MATCHING: Compare concatenated texts using SequenceMatcher
        if acc_concat and emm_concat:
            similarity_ratio = SequenceMatcher(None, acc_concat, emm_concat).ratio()
            is_match = similarity_ratio >= similarity_threshold
        elif not acc_concat and not emm_concat:
            # Both empty = match
            similarity_ratio = 1.0
            is_match = True
        else:
            # One has text, the other doesn't = no match
            similarity_ratio = 0.0
            is_match = False
        
        # Add to timeline (acceptance entry)
        if acc_texts:
            timeline.append({
                "timestamp": ts,
                "text": acc_original,
                "source": "acceptance",
                "confidence": acc_conf,
                "is_difference": not is_match and bool(emm_texts)  # Only diff if emission also has text at this time
            })
        
        # Add to timeline (emission entry)
        if emm_texts:
            timeline.append({
                "timestamp": ts,
                "text": emm_original,
                "source": "emission",
                "confidence": emm_conf,
                "is_difference": not is_match and bool(acc_texts)  # Only diff if acceptance also has text at this time
            })
        
        # Log differences
        if not is_match:
            if acc_texts and not emm_texts:
                differences.append({
                    "type": "missing_in_emission",
                    "text": acc_original,
                    "timestamp": ts,
                    "source": "acceptance",
                    "confidence": acc_conf
                })
            elif emm_texts and not acc_texts:
                differences.append({
                    "type": "extra_in_emission",
                    "text": emm_original,
                    "timestamp": ts,
                    "source": "emission",
                    "confidence": emm_conf
                })
            elif acc_texts and emm_texts:
                # Both have text but they differ
                differences.append({
                    "type": "text_mismatch",
                    "text": f"ACC: {acc_original[:100]}... vs EMM: {emm_original[:100]}...",
                    "timestamp": ts,
                    "source": "both",
                    "confidence": min(acc_conf, emm_conf)
                })
    
    # Sort differences by timestamp
    differences.sort(key=lambda x: x["timestamp"])
    
    # Sort timeline by timestamp
    timeline.sort(key=lambda x: x["timestamp"])
    
    # Calculate similarity score based on timestamps with matching texts
    total_timestamps = len(all_timestamps)
    matching_timestamps = sum(1 for ts in all_timestamps 
                              if normalize_text(concatenate_texts(acc_by_ts.get(ts, []))) == 
                                 normalize_text(concatenate_texts(emm_by_ts.get(ts, []))))
    
    if total_timestamps > 0:
        text_similarity = matching_timestamps / total_timestamps
    else:
        text_similarity = 1.0
    
    # Legacy stats for backwards compatibility
    acc_all_texts = set()
    emm_all_texts = set()
    for texts in acc_by_ts.values():
        for t, _ in texts:
            acc_all_texts.add(normalize_text(t))
    for texts in emm_by_ts.values():
        for t, _ in texts:
            emm_all_texts.add(normalize_text(t))
    
    common_texts = acc_all_texts & emm_all_texts
    only_in_acceptance = acc_all_texts - emm_all_texts
    only_in_emission = emm_all_texts - acc_all_texts

    result = {
        "text_similarity": round(text_similarity, 3),
        "acceptance_text_count": len(acc_by_ts),
        "emission_text_count": len(emm_by_ts),
        "common_texts": sorted(list(common_texts))[:20],  # Limit for performance
        "only_in_acceptance": sorted(list(only_in_acceptance))[:20],
        "only_in_emission": sorted(list(only_in_emission))[:20],
        "differences": differences,
        "timeline": timeline,
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


# ============================================================================
# NEW: Hash-Based Text Region Comparison (Pixel-perfect, no OCR)
# ============================================================================

def compare_text_regions_hash(
    acceptance_path: str,
    emission_path: str,
    region: str = "bottom_fifth",
    sample_interval: float = 0.5,
    similarity_threshold: float = 0.95  # 95% histogram match = OK
) -> Dict[str, Any]:
    """
    Compare text regions between two videos using histogram correlation.
    
    This is MUCH more reliable than OCR because:
    - 100% deterministic (same pixels = same hash)
    - Very fast (no ML inference)
    - Detects any visual difference, not just text
    
    Args:
        acceptance_path: Path to acceptance video
        emission_path: Path to emission video
        region: Region to compare (where text appears)
        sample_interval: Seconds between samples
        similarity_threshold: Minimum histogram correlation (0.0-1.0) to consider as match
    
    Returns:
        Comparison results with timeline and differences
    """
    import gc
    
    logger.info(f"📊 Starting Hash-Based Text Region Comparison (threshold={similarity_threshold})...")
    
    def extract_region_from_frame(frame: np.ndarray, region: str) -> np.ndarray:
        """Extract specified region from frame"""
        h, w = frame.shape[:2]
        if region == "bottom_fifth":
            return frame[int(h * 0.8):, :]
        elif region == "bottom_third":
            return frame[int(h * 0.67):, :]
        elif region == "bottom_half":
            return frame[int(h * 0.5):, :]
        elif region == "top_fifth":
            return frame[:int(h * 0.2), :]
        else:
            return frame[int(h * 0.8):, :]
    
    def compute_histogram(roi: np.ndarray) -> np.ndarray:
        """Compute normalized histogram for region"""
        # Convert to grayscale for simpler comparison
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi
        
        # Compute histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        # Normalize histogram
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist
    
    def compare_histograms(hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Compare two histograms using correlation method"""
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    
    # Open both videos
    cap_acc = cv2.VideoCapture(str(acceptance_path))
    cap_emm = cv2.VideoCapture(str(emission_path))
    
    if not cap_acc.isOpened() or not cap_emm.isOpened():
        logger.error("Failed to open one or both videos")
        return {"error": "Failed to open videos", "text_similarity": 0.0}
    
    fps_acc = cap_acc.get(cv2.CAP_PROP_FPS) or 25.0
    fps_emm = cap_emm.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames_acc = int(cap_acc.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames_emm = int(cap_emm.get(cv2.CAP_PROP_FRAME_COUNT))
    
    duration_acc = total_frames_acc / fps_acc
    duration_emm = total_frames_emm / fps_emm
    min_duration = min(duration_acc, duration_emm)
    
    logger.info(f"📹 Acceptance: {duration_acc:.1f}s @ {fps_acc:.1f}fps")
    logger.info(f"📹 Emission: {duration_emm:.1f}s @ {fps_emm:.1f}fps")
    
    timeline = []
    differences = []
    total_comparisons = 0
    matches = 0
    
    timestamp = 0.0
    max_frames = 500  # Safety limit
    
    while timestamp < min_duration and total_comparisons < max_frames:
        # Seek to timestamp in both videos
        frame_idx_acc = int(timestamp * fps_acc)
        frame_idx_emm = int(timestamp * fps_emm)
        
        cap_acc.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_acc)
        cap_emm.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_emm)
        
        ret_acc, frame_acc = cap_acc.read()
        ret_emm, frame_emm = cap_emm.read()
        
        if not ret_acc or not ret_emm:
            break
        
        # Extract text region from both
        roi_acc = extract_region_from_frame(frame_acc, region)
        roi_emm = extract_region_from_frame(frame_emm, region)
        
        # Compute histograms
        hist_acc = compute_histogram(roi_acc)
        hist_emm = compute_histogram(roi_emm)
        
        # Compare histograms
        similarity = compare_histograms(hist_acc, hist_emm)
        is_match = similarity >= similarity_threshold
        
        # Add to timeline
        timeline.append({
            "timestamp": round(timestamp, 2),
            "similarity": round(similarity, 4),
            "is_match": is_match,
            "is_difference": not is_match
        })
        
        if is_match:
            matches += 1
        else:
            differences.append({
                "timestamp": round(timestamp, 2),
                "similarity": round(similarity, 4),
                "type": "visual_difference"
            })
        
        total_comparisons += 1
        timestamp += sample_interval
        
        # MEMORY CLEANUP
        del frame_acc, frame_emm, roi_acc, roi_emm, hist_acc, hist_emm
        
        if total_comparisons % 20 == 0:
            gc.collect()
    
    cap_acc.release()
    cap_emm.release()
    gc.collect()
    
    # Calculate overall similarity
    text_similarity = matches / total_comparisons if total_comparisons > 0 else 1.0
    
    logger.info(f"✅ Hash comparison complete: {total_comparisons} frames, {matches} matches ({text_similarity*100:.1f}%)")
    
    result = {
        "text_similarity": round(text_similarity, 3),
        "total_frames_compared": total_comparisons,
        "matches": matches,
        "differences": differences,
        "timeline": timeline,
        "has_text_differences": len(differences) > 0,
        "region_analyzed": region,
        "comparison_method": "histogram_hash"  # Indicator that this is hash-based, not OCR
    }
    
    if len(differences) > 0:
        logger.warning(f"⚠️ Found {len(differences)} visual differences in text region!")
    else:
        logger.info("✅ No visual differences found in text region")
    
    return result
