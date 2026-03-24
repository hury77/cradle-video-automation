import os
import sys
from pathlib import Path
import logging

# Add backend dir to python path
sys.path.append(str(Path(__file__).parent))

from models.database import engine, SessionLocal, Base
from models.models import WhisperHallucination, HallucinationMatchType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    # Create the new table (create_all is safe, it won't drop existing tables)
    logger.info("Creating whisper_hallucinations table if it doesn't exist...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if we already seeded
        count = db.query(WhisperHallucination).count()
        if count == 0:
            logger.info("Seeding initial hallucination phrases...")
            
            initial_phrases = [
                # Common multilingual hallucinations
                ("amara.org", None, HallucinationMatchType.CONTAINS),
                ("subtitles by", None, HallucinationMatchType.CONTAINS),
                ("captioned by", None, HallucinationMatchType.CONTAINS),
                ("transcribed by", None, HallucinationMatchType.CONTAINS),
                ("sous-titres", None, HallucinationMatchType.CONTAINS),
                ("legendas pela comunidade", None, HallucinationMatchType.CONTAINS),
                
                # German Whisper hallucinations
                ("ja, das war's", "de", HallucinationMatchType.CONTAINS),
                ("ja das wars", "de", HallucinationMatchType.CONTAINS),
                ("vielen dank", "de", HallucinationMatchType.CONTAINS),
                ("tschüss", "de", HallucinationMatchType.CONTAINS),
                ("untertitel", "de", HallucinationMatchType.CONTAINS),
                ("danke fürs zuschauen", "de", HallucinationMatchType.CONTAINS),
                ("bis zum nächsten mal", "de", HallucinationMatchType.CONTAINS),
                
                # English silence hallucinations
                ("thanks for watching", "en", HallucinationMatchType.CONTAINS),
                ("thank you for watching", "en", HallucinationMatchType.CONTAINS),
                ("please subscribe", "en", HallucinationMatchType.CONTAINS),
                ("like and subscribe", "en", HallucinationMatchType.CONTAINS),
                
                # EXACT MATCHES (Short words)
                ("you", "en", HallucinationMatchType.EXACT),
                ("you.", "en", HallucinationMatchType.EXACT),
            ]
            
            for phrase, lang, match_type in initial_phrases:
                h = WhisperHallucination(
                    phrase=phrase,
                    language=lang,
                    match_type=match_type,
                    is_active=True
                )
                db.add(h)
                
            db.commit()
            logger.info(f"Successfully seeded {len(initial_phrases)} phrases.")
        else:
            logger.info(f"Found {count} existing hallucinations, skipping seed.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
