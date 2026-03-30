import logging
import json
from typing import Dict, Any, List, Optional


logger = logging.getLogger(__name__)

class AnalystService:
    """
    Agent 2: Analyst - "Mózg" 🧠
    Uses local LLM (Ollama) to analyze comparison results and provide human-like reasoning.
    """

    def __init__(self, model: str = "llama3"):
        self.model = model
        self.host = "http://localhost:11434"
        
    def analyze_job_results(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze comparison results and generate a verdict with reasoning.
        
        Args:
            job_data: A dictionary containing:
                - overall_similarity: float (0-1)
                - frames_with_differences: int
                - total_frames: int
                - audio_transcription_diff: str (optional)
                - audio_similarity: float (optional)
                - client_name: str
                - cradle_id: str
                
        Returns:
            Dict with 'verdict', 'reasoning', and 'confidence'
        """
        logger.info(f"🧠 Analyst Brain: Analyzing job {job_data.get('job_id')} for client {job_data.get('client_name')}")
        
        # Construct the system prompt with strict numerical thresholds (SOUL.md compliance)
        system_prompt = (
            "Jesteś profesjonalnym ekspertem QA w dziedzinie postprodukcji wideo dla firmy Cradle. "
            "Twoim zadaniem jest rygorystyczna analiza wyników porównania plików: Acceptance (wzorzec) i Emission (gotowy plik).\n\n"
            "ZASADY DECYZYJNE (TRUTH TABLE - NAJWAŻNIEJSZE):\n"
            "1. OBRAZ (overall_similarity / video_similarity):\n"
            "   - 1.00: Idealne dopasowanie -> APPROVE\n"
            "   - 0.98 - 0.999: Akceptowalne dla niskiej/średniej czułości -> APPROVE\n"
            "   - 0.95 - 0.979: Drobne różnice / kompresja -> REVIEW (QA musi to sprawdzić)\n"
            "   - Poniżej 0.95 (np. 0.57): KRYTYCZNY BŁĄD / BŁĘDNY PLIK -> REJECT\n"
            "2. GŁOŚNOŚĆ (LUFS):\n"
            "   - Różnica <= 1.0 LUFS: Akceptowalne -> APPROVE\n"
            "   - Różnica > 1.0 LUFS: Ryzyko błędu -> REVIEW\n"
            "   - Różnica > 2.0 LUFS: Poważna rozbieżność -> REJECT\n"
            "3. TEKST (Whisper / audio_transcription):\n"
            "   - Jeśli text_similarity >= 0.98: Transkrypcje są zgodne -> OK\n"
            "   - Jeśli text_similarity 0.90 - 0.97: Sprawdź word_differences_sample! Jeśli zawiera różnice w nazwach własnych (marki, produkty) -> REJECT. Drobne błędy STT (akcenty, wielkie litery) -> APPROVE.\n"
            "   - Jeśli text_similarity < 0.90: Poważne różnice w treści -> REJECT\n"
            "   - Jeśli status = 'not_run': Ignoruj audio_transcription (STT nie zostało uruchomione)\n\n"
            "PAMIĘTAJ: Lepiej dać REVIEW niż błędny APPROVE. Jeśli masz jakiekolwiek wątpliwości lub wartość 0.57 wydaje Ci się 'wysoka' - MYLISZ SIĘ. 0.57 to REJECT.\n\n"
            "Odpowiadaj ZAWSZE w formacie JSON:\n"
            "{\n"
            "  \"verdict\": \"approve\" | \"reject\" | \"review\",\n"
            "  \"reasoning\": \"krótkie uzasadnienie w języku polskim, odwołaj się do KONKRETNYCH LICZB (similarity, LUFS)\",\n"
            "  \"confidence\": 0.0 - 1.0\n"
            "}"
        )

        # Prepare context data for the prompt
        user_prompt = f"Oto wyniki automatycznej analizy:\n{json.dumps(job_data, indent=2)}\n\nNa podstawie tych danych, jaki jest Twój werdykt?"

        import ollama
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                options={
                    'temperature': 0.1,  # Keep it deterministic
                    'num_predict': 250,   # Allow for reasoning
                },
                keep_alive=0  # IMPORTANT: Unload model from RAM/VRAM immediately after inference
            )

            content = response['message']['content']
            
            # Try to find JSON in the response (sometimes LLMs wrap it in triple backticks)
            try:
                # Basic cleaning
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                analysis = json.loads(content)
                
                # Validation
                if "verdict" not in analysis:
                    analysis["verdict"] = "review"
                if "reasoning" not in analysis:
                    analysis["reasoning"] = "Analiza AI zakończona bez szczegółowego uzasadnienia."
                
                logger.info(f"✅ AI Analysis complete: {analysis['verdict']} (confidence: {analysis.get('confidence')})")
                return analysis

            except (json.JSONDecodeError, IndexError) as je:
                logger.error(f"❌ Failed to parse AI JSON response: {je}\nRaw content: {content}")
                return {
                    "verdict": "review",
                    "reasoning": f"Błąd przetwarzania odpowiedzi AI. Surowa odpowiedź: {content[:100]}...",
                    "confidence": 0.0
                }

        except Exception as e:
            logger.error(f"❌ AI Service Error: {e}")
            return {
                "verdict": "review",
                "reasoning": f"Usługa AI (Ollama) jest niedostępna lub zwróciła błąd: {str(e)}",
                "confidence": 0.0
            }


def get_analyst() -> AnalystService:
    """Lazy loader for AnalystService singleton"""
    return AnalystService()
