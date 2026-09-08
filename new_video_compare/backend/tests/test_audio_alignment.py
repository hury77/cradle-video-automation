import pytest
from services.audio_service import compare_transcripts

def test_aligned_dialog_timeline_normal_case():
    """Test normal alignment with punctuation differences and minor word changes."""
    transcript_a = {
        "text": "Demandez à ma mère ? Vous êtes toujours aussi calme. C'est un don.",
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Demandez à ma mère ?"},
            {"start": 2.0, "end": 4.0, "text": "Vous êtes toujours aussi calme."},
            {"start": 4.0, "end": 6.0, "text": "C'est un don."}
        ]
    }
    
    transcript_b = {
        "text": "Demandez à ma mère. Vous êtes toujours aussi calme. C'est à don.",
        "segments": [
            {"start": 0.1, "end": 2.1, "text": "Demandez à ma mère. Vous"},
            {"start": 2.1, "end": 4.1, "text": "êtes toujours aussi calme. C'est"},
            {"start": 4.1, "end": 6.1, "text": "à don."}
        ]
    }
    
    result = compare_transcripts(transcript_a, transcript_b)
    timeline = result["timeline_data"]["aligned_dialog_timeline"]
    
    assert len(timeline) == 3
    
    # Segment 0: Punctuation difference only, should not have mismatch
    assert timeline[0]["acceptance"] == "Demandez à ma mère ?"
    assert timeline[0]["emission"] == "Demandez à ma mère."
    assert timeline[0]["has_mismatch"] is False
    
    # Segment 1: Exact match
    assert timeline[1]["acceptance"] == "Vous êtes toujours aussi calme."
    assert timeline[1]["emission"] == "Vous êtes toujours aussi calme."
    assert timeline[1]["has_mismatch"] is False
    
    # Segment 2: Word difference ("un" -> "à")
    assert timeline[2]["acceptance"] == "C'est un don."
    assert timeline[2]["emission"] == "C'est à don."
    assert timeline[2]["has_mismatch"] is True

def test_aligned_dialog_timeline_empty_emission():
    """Test edge case where Emission segment is completely empty (e.g. VAD dithering)."""
    transcript_a = {
        "text": "Hello world",
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "Hello world"}
        ]
    }
    
    transcript_b = {
        "text": "",
        "segments": []
    }
    
    result = compare_transcripts(transcript_a, transcript_b)
    timeline = result["timeline_data"]["aligned_dialog_timeline"]
    
    assert len(timeline) == 1
    assert timeline[0]["acceptance"] == "Hello world"
    assert timeline[0]["emission"] == ""
    assert timeline[0]["has_mismatch"] is True

def test_aligned_dialog_timeline_pure_delete():
    """Test pure delete at the end of Acceptance without any insert/replace."""
    transcript_a = {
        "text": "Start the engine now",
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "Start the"},
            {"start": 1.0, "end": 2.0, "text": "engine now"}
        ]
    }
    
    transcript_b = {
        "text": "Start the",
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "Start the"}
        ]
    }
    
    result = compare_transcripts(transcript_a, transcript_b)
    timeline = result["timeline_data"]["aligned_dialog_timeline"]
    
    assert len(timeline) == 2
    
    assert timeline[0]["acceptance"] == "Start the"
    assert timeline[0]["emission"] == "Start the"
    assert timeline[0]["has_mismatch"] is False
    
    assert timeline[1]["acceptance"] == "engine now"
    assert timeline[1]["emission"] == ""
    assert timeline[1]["has_mismatch"] is True
