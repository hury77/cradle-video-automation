import logging
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AnalystService:
    """
    Agent 2: Analyst - "Mózg" 🧠
    
    Uses local LLM (Ollama) to analyze comparison results and provide human-like reasoning.
    
    KEY PRINCIPLE (SOUL.md): The qa_decisions table is the Knowledge Base — the sacred
    source of truth. It must never be destroyed or overwritten without reason. Every human
    override is a lesson. This service reads from the KB per-client to improve accuracy.
    """

    def __init__(self, model: str = "llama3"):
        self.model = model
        self.host = "http://localhost:11434"

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    def analyze_job_results(
        self, job_data: Dict[str, Any], db=None
    ) -> Dict[str, Any]:
        """
        Analyze comparison results and generate a verdict with reasoning.

        Args:
            job_data: Metrics dictionary from comparison_service._run_ai_analyst()
            db: Optional SQLAlchemy Session — used to load per-client historical context.
                If None, analysis runs without historical context (fallback).

        Returns:
            Dict with 'verdict', 'reasoning', and 'confidence'
        """
        client_name = job_data.get("client_name", "")
        job_id = job_data.get("job_id")
        logger.info(f"🧠 Analyst Brain: Analyzing job {job_id} for client '{client_name}'")

        # Load per-client historical context from KB (SOUL.md: Ucz się per-klient)
        historical_context = []
        if db and client_name:
            historical_context = self._load_historical_context(db, client_name, job_id)
            if historical_context:
                logger.info(
                    f"📚 KB: Loaded {len(historical_context)} historical decisions for '{client_name}'"
                )
            else:
                logger.info(
                    f"📚 KB: No past decisions for '{client_name}' — using rules only"
                )

        # Build prompt with rules + KB context
        system_prompt = self._build_system_prompt(historical_context)
        user_prompt = (
            f"Oto wyniki automatycznej analizy:\n{json.dumps(job_data, indent=2)}\n\n"
            "Na podstawie tych danych i historii decyzji, jaki jest Twój werdykt?"
        )

        # Store metrics for fallback reasoning generation (used if LLM returns empty reasoning)
        self._last_metrics = job_data

        import ollama
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",   # Forces Ollama to return valid JSON (grammar sampling)
                options={
                    "temperature": 0.1,   # Deterministic — rules over creativity
                    "num_predict": 400,   # Polish JSON verdict ~150-300 tokens — 1024 caused 160s+ calls
                },
                keep_alive=0,  # Unload model immediately to free RAM (M4 optimization)
            )

            content = response["message"]["content"]
            return self._parse_response(content)

        except Exception as e:
            logger.error(f"❌ AI Service Error: {e}")
            return {
                "verdict": "review",
                "reasoning": f"Usługa AI (Ollama) jest niedostępna: {str(e)}",
                "confidence": 0.0,
            }

    # ──────────────────────────────────────────────────────────────────────────
    # KNOWLEDGE BASE: Per-client historical context
    # ──────────────────────────────────────────────────────────────────────────

    def _load_historical_context(
        self, db, client_name: str, current_job_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        """
        Load the most relevant past QA decisions for this client from the Knowledge Base.

        SOUL.md principle: The KB is sacred — we only READ here, never modify.
        Priority order:
          1. Human overrides (decided_by='human') — the most valuable lessons
          2. AI decisions that were NOT overridden — confirmed correct patterns
        Limit: 8 records max to keep the prompt focused and avoid token bloat.
        """
        try:
            from models.models import QADecision

            # --- Human decisions first (SOUL: overrides are the most valuable lessons)
            human_decisions = (
                db.query(QADecision)
                .filter(
                    QADecision.client_name == client_name,
                    QADecision.decided_by == "human",
                    QADecision.metrics_snapshot.isnot(None),
                    QADecision.job_id != current_job_id,
                )
                .order_by(QADecision.id.desc())
                .limit(5)
                .all()
            )

            # --- AI decisions that were not overridden (confirmed patterns)
            ai_decisions = (
                db.query(QADecision)
                .filter(
                    QADecision.client_name == client_name,
                    QADecision.decided_by == "agent",
                    QADecision.metrics_snapshot.isnot(None),
                    QADecision.job_id != current_job_id,
                )
                .order_by(QADecision.id.desc())
                .limit(3)
                .all()
            )

            # Combine: human first, then AI (max 8 total)
            all_decisions = human_decisions + ai_decisions

            if not all_decisions:
                return []

            context = []
            for d in all_decisions:
                snap = d.metrics_snapshot or {}
                entry = {
                    "verdict": d.verdict.value,
                    "decided_by": d.decided_by,
                    # Key metrics that drove the decision
                    "overall_similarity": snap.get("overall_similarity"),
                    "video_differences": snap.get("video_differences_count"),
                    "audio_similarity": snap.get("audio_similarity"),
                    "lufs_difference": snap.get("audio_loudness", {}).get("lufs_difference")
                        if isinstance(snap.get("audio_loudness"), dict) else None,
                    "text_similarity": snap.get("audio_transcription", {}).get("text_similarity")
                        if isinstance(snap.get("audio_transcription"), dict) else None,
                    # Human reasoning: use comment or override_reason as the richest signal
                    "human_comment": d.comment or None,
                    "override_reason": d.override_reason or None,
                    "ai_was_wrong": d.override_reason is not None,  # explicit flag
                }
                context.append(entry)

            logger.debug(
                f"📚 KB context for '{client_name}': "
                f"{len(human_decisions)} human + {len(ai_decisions)} AI decisions"
            )
            return context

        except Exception as e:
            # KB read errors must NEVER block the analysis — just proceed without context
            logger.warning(f"⚠️ Failed to load KB context for '{client_name}': {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────────
    # PROMPT CONSTRUCTION
    # ──────────────────────────────────────────────────────────────────────────

    def _build_system_prompt(self, historical_context: List[Dict]) -> str:
        """
        Build system prompt with SOUL.md Truth Table + per-client KB context.
        Historical context is formatted as few-shot examples for the LLM.
        """
        base_rules = (
            "Jesteś profesjonalnym ekspertem QA w dziedzinie postprodukcji wideo dla firmy Cradle. "
            "Twoim zadaniem jest rygorystyczna i UCZCIWA analiza wyników porównania plików: Acceptance (wzorzec) i Emission (gotowy plik).\n\n"
            "⛔ TWARDA REGUŁA (ZERO WYJĄTKÓW):\n"
            "   1. Jeśli overall_similarity lub video_similarity < 0.95, werdykt MUSI być REJECT lub REVIEW. Nie wolno Ci ignorować tej reguły.\n"
            "   2. Jeśli stt_skipped = true oraz audio_similarity >= 0.98 (I OBA PLIKI NIE SĄ NIEME - patrz reguła 5), Twoje uzasadnienie MUSI zawierać jasny przekaz: 'Transkrypcja została pominięta dla optymalizacji z powodu braku różnic w warstwie audio.'\n"
            "   3. NIGDY nie nazywaj różnicy LUFS > 1.0 'akceptowalną' lub 'idealną'. Jeśli system zgłasza has_loudness_issue: true, Twoim obowiązkiem jest to zaraportować jako BŁĄD.\n"
            "   4. NIGDY nie pisz 'brak różnic w tekście', jeśli text_similarity < 1.0 lub is_text_match = false. Nawet jedna różnica w słowach to RÓŻNICA.\n"
            "   5. ZGODNOŚĆ DŁUGOŚCI:\n"
            "      - Jeśli is_arpp_slate = true: system automatycznie wyrównał pliki ARPP/Clearcast (11s planszy). Dodaj o tym wzmiankę w uzasadnieniu.\n"
            "      - Jeśli is_arpp_slate = false ORAZ duration_difference > 0.5: MUSISZ odrzucić plik (REJECT). W uzasadnieniu napisz wyraźnie, że pliki mają różną długość.\n\n"
            "ZASADY DECYZYJNE (TRUTH TABLE — bezwzględne progi):\n"
            "1. OBRAZ (overall_similarity / video_similarity):\n"
            "   - 1.00: Idealne dopasowanie → APPROVE\n"
            "   - 0.98 - 0.999: Akceptowalne (kompresja) → APPROVE\n"
            "   - 0.95 - 0.979: Drobne różnice → REVIEW\n"
            "   - Poniżej 0.95: KRYTYCZNY BŁĄD → REJECT\n"
            "2. GŁOŚNOŚĆ (LUFS):\n"
            "   - Różnica <= 1.0 LUFS: OK → APPROVE\n"
            "   - Różnica > 1.0 LUFS: Zazwyczaj REVIEW lub REJECT.\n"
            "   ⚠️ WYJĄTEK DLA SPECYFIKACJI (LUFS OVERRIDE):\n"
            "   Jeśli ogólne podobieństwo wideo (overall_similarity) wynosi >= 0.98 ORAZ tekst mowy (STT) zgadza się w 100% (is_text_match = true lub brak mowy),\n"
            "   wtedy zignoruj różnicę w głośności i ZATWIERDŹ plik (APPROVE). W uzasadnieniu musisz zaznaczyć: 'Wykryto różnicę głośności wynikającą ze specyfikacji eksportu, ale ze względu na całkowitą zgodność wideo i ścieżki lektorskiej plik zostaje zaakceptowany.'\n"
            "3. AUDIO SIMILARITY (MFCC/spectral):\n"
            "   ⚠️ Złota reguła: Drobne różnice spektralne przy w 100% zgodnym tekście i głośności to zazwyczaj nieszkodliwy wynik innej kompresji eksportu.\n"
            "   - Jeśli stt_is_match = true oraz has_loudness_issue = false: Spadki audio_similarity do 0.75 można ignorować → APPROVE. Poniżej 0.75 → REVIEW.\n"
            "   - Jeśli tekst mowy lub głośność wykazują błędy: Wtedy wymagany próg podobieństwa wynosi 0.90. Spadek poniżej 0.90 → REVIEW.\n"
            "   ⚠️ Z samego powodu spadku audio_similarity NIGDY nie odrzucaj pliku (REJECT). Maksymalna reakcja to REVIEW.\n"
            "4. TEKST (Whisper):\n"
            "   - word_count_a = 0 i word_count_b = 0: W uzasadnieniu napisz 'Brak mowy / VO.'\n"
            "   - text_similarity = 1.0 (is_text_match=true): Zgodne → OK\n"
            "   - text_similarity < 1.0 (is_text_match=false): Sprawdź stt_segment_differences (oraz word_differences_sample)!\n"
            "     - Opieraj się na segment_differences aby zobaczyć CO zniknęło/pojawiło się W KTÓREJ SEKUNDZIE.\n"
            "     - Jeśli to fonetyczne warianty (np. 'Opel' vs 'Opl'): REVIEW (opisz to jako artefakt STT).\n"
            "     - Jeśli to inne słowa, wstawki lub braki (np. wyciszone słowo w emisji): REJECT i napisz w której sekundzie to wystąpiło.\n"
            "     ⚠️ NIGDY nie ignoruj różnic w tekście tylko dlatego, że podobieństwo wynosi 97%.\n"
            "5. BRAK AUDIO LUB CISZA:\n"
            "   - Jeśli audio_similarity = 0.0 lub zgłasza błąd 'No audio streams found': Oznacza to BRAK ŚCIEŻEK AUDIO.\n"
            "   - Jeśli w metrykach audio_loudness wartości acceptance_lufs = null ORAZ emission_lufs = null: Oznacza to, że PLIKI SĄ CAŁKOWICIE NIEME (zawierają wyciszoną ścieżkę dźwiękową).\n"
            "   - W obu powyższych przypadkach MUSISZ wyraźnie napisać w uzasadnieniu: 'Brak ścieżek dźwiękowych w obu plikach' lub 'Oba pliki są całkowicie nieme'. NIGDY nie nazywaj tego 'pełną zgodnością audio', 'brakiem różnic w głośności' ani nie pisz o pominiętej transkrypcji.\n\n"
            "HIERARCHIA PRAWDY:\n"
            "   1. TWARDE REGUŁY (Truth Table powyżej) — nadrzędne nad WSZYSTKIM.\n"
            "   2. DECYZJE CZŁOWIEKA (Baza Wiedzy) — wyjątki specyficzne dla klienta.\n"
            "   3. DECYZJE AI — tylko sugestie. Jeśli łamią progi 1-4, ignoruj je.\n\n"
            "⚠️ ZASADA APPROVE:\n"
            "   Jeśli wszystkie metryki mieszczą się w progach APPROVE (obraz >= 0.98, LUFS <= 1.0, audio >= 0.95, tekst = 1.0 lub brak mowy), "
            "Twój werdykt MUSI być APPROVE. Nie dawaj REVIEW bez KONKRETNEGO powodu — podaj dokładnie który parametr jest poza normą.\n"
            "   REVIEW to decyzja dla niejednoznacznych przypadków, NIE dla idealnych wyników.\n\n"
            "STYL WYPOWIEDZI (BARDZO WAŻNE):\n"
            "   - Pisz naturalnie, jak doświadczony pracownik QA oceniający plik, a nie jak maszyna raportująca logi czy kopiująca reguły.\n"
            "   - Zamiast suchego 'Wszystkie metryki mieszczą się w progach', napisz np. 'Idealne dopasowanie w obrazie (1.0) oraz brak różnic w głośności. Tekstowa analiza jest zgodna.'\n"
            "   - Buduj pełne, płynne zdania. Zawsze uwzględniaj kluczowe liczby, ale w naturalnym kontekście.\n"
            "   - Nie kopiuj fragmentów tego promptu do odpowiedzi!\n\n"
            "PAMIĘTAJ: Twoim celem jest UCZCIWA i ludzka w brzmieniu analiza.\n\n"
        )

        # Inject per-client KB context as few-shot examples
        kb_section = ""
        if historical_context:
            human_examples = [e for e in historical_context if e["decided_by"] == "human"]
            ai_examples = [e for e in historical_context if e["decided_by"] == "agent"]

            kb_section += (
                "BAZA WIEDZY — HISTORIA DECYZJI DLA TEGO KLIENTA:\n"
                "⚠️ UWAGA: Poniższa historia służy do zachowania spójności, ale NIGDY nie może unieważnić TWARDYCH REGUŁ (chyba, że jest to decyzja CZŁOWIEKA).\n\n"
            )

            if human_examples:
                kb_section += "📌 DECYZJE CZŁOWIEKA (Najwyższa ranga — zweryfikowane standardy klienta):\n"
                for i, ex in enumerate(human_examples, 1):
                    kb_section += (
                        f"  Przykład {i}: similarity={ex['overall_similarity']}, "
                        f"lufs_diff={ex['lufs_difference']}, text_sim={ex['text_similarity']} "
                        f"→ {ex['verdict'].upper()}"
                    )
                    if ex.get("human_comment"):
                        kb_section += f"\n    💬 Komentarz QA: \"{ex['human_comment']}\""
                    if ex.get("override_reason"):
                        kb_section += f"\n    ✏️ Powód korekty AI: \"{ex['override_reason']}\""
                    if ex.get("ai_was_wrong"):
                        kb_section += "\n    ⚠️ AI POMYLIŁO SIĘ w tym przypadku — uważaj na podobne wzorce!"
                    kb_section += "\n"

            if ai_examples:
                kb_section += "\n📊 DECYZJE AI (Niesprawdzone sugestie — mogą zawierać błędy! Jeśli łamią progi z punktów 1-4, ignoruj je):\n"
                for i, ex in enumerate(ai_examples, 1):
                    kb_section += (
                        f"  Przykład {i}: similarity={ex['overall_similarity']}, "
                        f"lufs_diff={ex['lufs_difference']} "
                        f"→ {ex['verdict'].upper()}\n"
                    )

            kb_section += (
                "\nWykorzystaj tę historię jako kontekst — jeśli nowy job ma podobne "
                "metryki do powyższych, prawdopodobnie ta sama decyzja jest prawidłowa. "
                "Jeśli AI myliło się w podobnych przypadkach — uwzględnij to.\n\n"
            )

        output_format = (
            "Odpowiadaj ZAWSZE w formacie JSON i BEZWZGLĘDNIE W JĘZYKU POLSKIM. Nie używaj języka angielskiego:\n"
            "{\n"
            "  \"verdict\": \"approve\" | \"reject\" | \"review\",\n"
            "  \"reasoning\": \"naturalne, ludzkie uzasadnienie po polsku z KONKRETNYMI LICZBAMI wplecionymi w tekst\",\n"
            "  \"confidence\": 0.0 - 1.0,\n"
            "  \"kb_used\": true | false\n"
            "}"
        )

        return base_rules + kb_section + output_format

    # ──────────────────────────────────────────────────────────────────────────
    # RULE-BASED REASONING (fallback when LLM returns empty reasoning)
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_rule_based_reasoning(self, verdict: str, metrics: dict) -> str:
        """
        Generate a deterministic, metric-based reasoning string when the LLM
        returns an empty `reasoning` field.

        Follows the Truth Table from SOUL.md / system prompt to produce
        a human-readable, auditable explanation.
        """
        if not metrics:
            return f"Werdykt: {verdict.upper()}. Brak metryk do wygenerowania uzasadnienia."

        parts = []

        # Video
        video_sim = metrics.get("video_similarity", metrics.get("overall_similarity"))
        diff_count = metrics.get("video_differences_count", 0)
        if video_sim is not None:
            video_sim = float(video_sim)
            if video_sim >= 0.98:
                parts.append(f"Obraz: zgodny (similarity={video_sim:.4f}, {diff_count} różnych klatek).")
            elif video_sim >= 0.95:
                parts.append(f"Obraz: drobne różnice (similarity={video_sim:.4f}, {diff_count} różnych klatek) — próg REVIEW.")
            else:
                parts.append(f"Obraz: KRYTYCZNA RÓŻNICA (similarity={video_sim:.4f}, {diff_count} różnych klatek) — poniżej progu 0.95.")

        # Audio similarity
        audio_sim = metrics.get("audio_similarity")
        
        # Check for completely missing audio
        audio_data = metrics.get("audio_analysis_data", {})
        transcription_data = metrics.get("audio_transcription", {})
        similarity_error = audio_data.get("similarity", {}).get("error", "") if isinstance(audio_data, dict) else ""
        
        is_missing_audio = False
        if audio_sim is None or (isinstance(audio_data, dict) and (audio_data.get("no_audio_tracks") or audio_data.get("has_audio") is False)):
            is_missing_audio = True
        elif audio_sim == 0.0:
            if "No audio streams found" in similarity_error or "FFmpeg failed" in similarity_error or "Format not recognised" in similarity_error:
                is_missing_audio = True

        if is_missing_audio:
            parts.append("Audio: brak ścieżki dźwiękowej w materiałach (plik niemy / GIF).")
        elif audio_sim is not None:
            audio_sim = float(audio_sim)
            if audio_sim >= 0.95:
                parts.append(f"Audio: akceptowalne (audio_similarity={audio_sim:.4f}).")
            elif audio_sim >= 0.90:
                parts.append(f"Audio: drobne różnice (audio_similarity={audio_sim:.4f}).")
            else:
                parts.append(f"Audio: POWAŻNE RÓŻNICE (audio_similarity={audio_sim:.4f}).")

        # LUFS
        if not is_missing_audio:
            loudness = metrics.get("audio_loudness", {})
            if isinstance(loudness, dict):
                lufs_diff = loudness.get("lufs_difference")
                if lufs_diff is not None:
                    lufs_diff = abs(float(lufs_diff))
                    if lufs_diff <= 1.0:
                        parts.append(f"Głośność: OK (|LUFS diff|={lufs_diff:.2f}).")
                    elif lufs_diff <= 2.0:
                        parts.append(f"Głośność: wyraźna rozbieżność (|LUFS diff|={lufs_diff:.2f}) — próg REVIEW.")
                    else:
                        parts.append(f"Głośność: KRYTYCZNA RÓŻNICA (|LUFS diff|={lufs_diff:.2f}) — próg REJECT.")

        # STT
        if not is_missing_audio:
            transcription = metrics.get("audio_transcription", {})
            if isinstance(transcription, dict):
                if transcription.get("status") == "not_run":
                    pass
                else:
                    text_sim = transcription.get("text_similarity")
                    skipped = transcription.get("skipped", False)
                    if skipped:
                        parts.append(
                            "Transkrypcja została pominięta dla optymalizacji z powodu braku różnic w warstwie audio."
                        )
                    elif text_sim is not None:
                        text_sim = float(text_sim)
                        # Check if there is actual speech
                        audio_data = metrics.get("audio_analysis_data", {})
                        stt_comp = audio_data.get("speech_to_text", {}).get("comparison", {}) if isinstance(audio_data, dict) else {}
                        if isinstance(stt_comp, dict) and stt_comp.get("word_count_a", -1) == 0 and stt_comp.get("word_count_b", -1) == 0:
                            parts.append("Transkrypcja: brak mowy / VO.")
                        elif text_sim >= 0.98:
                            parts.append(f"Transkrypcja: zgodna (text_similarity={text_sim:.4f}).")
                        else:
                            parts.append(f"Transkrypcja: różnice (text_similarity={text_sim:.4f}).")

        # Duration / ARPP
        duration_diff = metrics.get("duration_difference", 0.0)
        is_arpp = metrics.get("is_arpp_slate", False)
        
        if is_arpp:
            parts.append("Wyrównano format ARPP/Clearcast (ok. 11s planszy).")
        elif duration_diff > 0.5:
            parts.append(f"KRYTYCZNA RÓŻNICA: pliki różnią się długością o {duration_diff:.1f}s.")

        if not parts:
            return f"Werdykt: {verdict.upper()}. Automatyczna analiza na podstawie metryk."

        return " ".join(parts) + f" Końcowy werdykt: {verdict.upper()}."

    # ──────────────────────────────────────────────────────────────────────────
    # RESPONSE PARSING
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse LLM JSON response — language-agnostic, LLM-proof.

        Strategy:
        1. Find the FIRST '{' and LAST '}' and parse JSON between them.
        2. If no valid JSON found, use regex to extract verdict from free text
           (fallback for models that ignore format=json instruction).
        3. Only as last resort: return REVIEW with raw error excerpt.
        """
        import re
        raw_content = content  # Keep for error logging

        try:
            # Step 1: Try to find the JSON object directly by braces
            start = content.find('{')
            end = content.rfind('}')

            if start != -1 and end != -1 and end > start:
                json_str = content[start:end + 1]
                analysis = json.loads(json_str)
            else:
                # Step 2: Fallback — try stripping markdown code fences
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                analysis = json.loads(content)

            # Validate & sanitize
            original_verdict = str(analysis.get("verdict", "review")).lower().strip()
            verdict = original_verdict
            if verdict not in ("approve", "reject", "review"):
                logger.warning(f"⚠️ Unexpected verdict value '{verdict}' — defaulting to review")
                verdict = "review"
            analysis["verdict"] = verdict

            # If LLM skipped reasoning (common for small models on obvious cases),
            # generate a deterministic, metric-based explanation instead of the generic fallback.
            if "reasoning" not in analysis or not str(analysis.get("reasoning", "")).strip():
                logger.warning("⚠️ LLM returned empty reasoning — generating rule-based explanation.")
                analysis["reasoning"] = self._generate_rule_based_reasoning(verdict, self._last_metrics)

            # ── Deterministic Post-Processing for STT Skipped ─────────────────
            # Prevent LLM from hallucinating that "transcription is perfect" when it was skipped.
            if self._last_metrics.get("stt_skipped", False):
                reasoning = analysis.get("reasoning", "")
                required_msg = "Transkrypcja została pominięta dla optymalizacji z powodu braku różnic w warstwie audio."
                if required_msg not in reasoning:
                    import re
                    # Remove false claims about transcription being checked/perfect
                    reasoning = re.sub(r'(?i)(\s*(i|oraz)\s*transkrypcji)', '', reasoning)
                    reasoning = re.sub(r'(?i)(,\s*a)?\s*brak\s+różnic\s+w\s+(warstwie\s+)?(tekście|transkrypcji)\.?', '', reasoning)
                    reasoning = re.sub(r'(?i)(transkrypcja(\s+jest)?\s+(idealna|zgodna|identyczna))\.?', '', reasoning)
                    # Clean up any trailing spaces or misplaced periods before appending
                    reasoning = reasoning.replace(" .", ".").strip().rstrip(',')
                    # Append the required message
                    analysis["reasoning"] = f"{reasoning} {required_msg}".strip()
                    logger.info("🔧 Post-processing: Corrected LLM reasoning to explicitly mention skipped STT.")

            # ── Deterministic Post-Processing for Missing Audio ───────────────
            # Prevent LLM from saying "pełna zgodność audio" when there are no audio tracks
            audio_data = self._last_metrics.get("audio_analysis_data", {})
            audio_sim = self._last_metrics.get("audio_similarity")
            similarity_error = audio_data.get("similarity", {}).get("error", "") if isinstance(audio_data, dict) else ""
            
            is_missing_audio = False
            if audio_sim is not None and float(audio_sim) == 0.0:
                if "No audio streams found" in similarity_error or "FFmpeg failed" in similarity_error:
                    is_missing_audio = True

            if is_missing_audio:
                reasoning = analysis.get("reasoning", "")
                required_msg = "Brak ścieżek dźwiękowych w obu plikach."
                if required_msg not in reasoning:
                    import re
                    reasoning = re.sub(r'(?i)(\s*(i|oraz)\s*(audio|dźwięku|transkrypcji))', '', reasoning)
                    reasoning = re.sub(r'(?i)(,\s*a)?\s*brak\s+różnic\s+w\s+(warstwie\s+)?(audio|dźwięku|tekście|transkrypcji)\.?', '', reasoning)
                    reasoning = re.sub(r'(?i)((audio|dźwięk|transkrypcja)(\s+jest)?\s+(idealna|zgodna|identyczna|wzorowa))\.?', '', reasoning)
                    reasoning = re.sub(r'(?i)(pełna\s+zgodność\s+(warstwy\s+)?audio)\.?', '', reasoning)
                    reasoning = reasoning.replace(" .", ".").strip().rstrip(',')
                    analysis["reasoning"] = f"{reasoning} {required_msg}".strip()
                    logger.info("🔧 Post-processing: Corrected LLM reasoning to explicitly mention missing audio tracks.")

            # ── Deterministic Post-Processing for Missing VO ──────────────────
            # Prevent LLM from saying "Transkrypcja zgodna" when there is no voiceover
            if not is_missing_audio and not self._last_metrics.get("stt_skipped", False):
                stt_comp = audio_data.get("speech_to_text", {}).get("comparison", {}) if isinstance(audio_data, dict) else {}
                if isinstance(stt_comp, dict) and stt_comp.get("word_count_a", -1) == 0 and stt_comp.get("word_count_b", -1) == 0:
                    reasoning = analysis.get("reasoning", "")
                    required_msg = "Transkrypcja: brak mowy / VO."
                    if required_msg not in reasoning and "Brak mowy" not in reasoning:
                        import re
                        reasoning = re.sub(r'(?i)(Transkrypcja(:\s*)?(jest\s*)?(zgodna|identyczna|idealna|wzorowa))\.?', '', reasoning)
                        reasoning = reasoning.replace(" .", ".").strip().rstrip(',')
                        analysis["reasoning"] = f"{reasoning} {required_msg}".strip()
                        logger.info("🔧 Post-processing: Corrected LLM reasoning to explicitly mention missing VO.")

            # ── Deterministic Post-Processing for DOOH (no audio tracks) ────
            # DOOH files legitimately have no audio tracks. In this case:
            #   - audio_similarity = 0.0 (FFmpeg can't extract what isn't there)
            #   - lufs_difference = null (nothing to measure)
            #   - audio_transcription.text_similarity = 1.0 (both empty → match)
            # This is NOT a quality defect — audio absence in both files is OK.
            # If video matches perfectly, the verdict MUST be APPROVE.
            if analysis["verdict"] in ("reject", "review"):
                video_sim = self._last_metrics.get("overall_similarity", 1.0)
                audio_sim = self._last_metrics.get("audio_similarity")
                audio_loudness = self._last_metrics.get("audio_loudness", {})
                lufs_diff = audio_loudness.get("lufs_difference") if isinstance(audio_loudness, dict) else None
                has_loudness_issue = audio_loudness.get("has_loudness_issue", False) if isinstance(audio_loudness, dict) else False

                stt_data = self._last_metrics.get("audio_transcription", {})
                text_sim = stt_data.get("text_similarity") if isinstance(stt_data, dict) else None
                word_diffs = stt_data.get("word_differences_count", 0) if isinstance(stt_data, dict) else 0

                # DOOH pattern: no LUFS data, audio_sim=0.0, text perfectly matches (both empty)
                # OR asymmetric audio (one file has no audio streams) where we intentionally skip STT
                stt_skipped_reason = self._last_metrics.get("stt_skipped_reason", "")
                is_asymmetric_audio = stt_skipped_reason and "No audio streams in" in stt_skipped_reason

                is_no_audio = (
                    (
                        lufs_diff is None
                        and not has_loudness_issue
                        and audio_sim is not None and float(audio_sim) == 0.0
                        and (text_sim is None or text_sim == 1.0)
                        and word_diffs == 0
                    )
                    or is_asymmetric_audio
                )

                if is_no_audio and float(video_sim) >= 0.98:
                    analysis["verdict"] = "approve"
                    
                    reason_msg = "brak ścieżek dźwiękowych w obu plikach"
                    if is_asymmetric_audio:
                        if "acceptance" in stt_skipped_reason.lower():
                            reason_msg = "brak ścieżki dźwiękowej w pliku acceptance (oczekiwane w digital)"
                        else:
                            reason_msg = "brak ścieżki dźwiękowej w pliku emisji (oczekiwane w digital)"
                            
                    analysis["reasoning"] = (
                        f"Obraz: idealnie zgodny (similarity={video_sim:.4f}, 0 różnych klatek). "
                        f"Audio: {reason_msg} (DOOH — poprawny stan). "
                        "Brak różnic w treści. Końcowy werdykt: APPROVE."
                    )
                    logger.info(f"🔧 Post-processing: DOOH detected ({reason_msg}) — overriding to APPROVE.")

            # ── Deterministic Post-Processing for Minor Audio Differences ───
            # If everything else is perfect, allow audio similarity down to 0.85 as compression artifacts
            if analysis["verdict"] == "review":
                video_sim = self._last_metrics.get("overall_similarity", 1.0)
                audio_sim = self._last_metrics.get("audio_similarity")
                audio_loudness = self._last_metrics.get("audio_loudness", {})
                lufs_diff = audio_loudness.get("lufs_difference") if isinstance(audio_loudness, dict) else None
                abs_lufs = abs(float(lufs_diff)) if lufs_diff is not None else 0.0
                
                # Check STT matches
                stt_data = self._last_metrics.get("audio_transcription", {})
                stt_skipped = self._last_metrics.get("stt_skipped", False)
                
                is_stt_ok = False
                if stt_skipped:
                    is_stt_ok = True
                elif isinstance(stt_data, dict):
                    text_sim = stt_data.get("text_similarity")
                    if text_sim == 1.0:
                        is_stt_ok = True
                    else:
                        stt_comp = audio_data.get("speech_to_text", {}).get("comparison", {}) if isinstance(audio_data, dict) else {}
                        if isinstance(stt_comp, dict) and stt_comp.get("word_count_a", -1) == 0 and stt_comp.get("word_count_b", -1) == 0:
                            is_stt_ok = True

                if video_sim >= 0.98 and abs_lufs <= 1.0 and is_stt_ok:
                    if audio_sim is not None and float(audio_sim) >= 0.85:
                        analysis["verdict"] = "approve"
                        reasoning = analysis.get("reasoning", "")
                        import re
                        reasoning = re.sub(r'(?i)Końcowy werdykt:\s*(REVIEW|REJECT)', 'Końcowy werdykt: APPROVE', reasoning)
                        analysis["reasoning"] = reasoning.strip()
                        logger.info("🔧 Post-processing: Overriding to APPROVE — all metrics within acceptable thresholds.")

            # ── Deterministic Threshold Enforcers ─────────────────────────────
            # Run UNCONDITIONALLY — ensures hard thresholds override AI regardless of
            # whether it said approve, review, or reject (e.g. REVIEW when should be REJECT)
            current_reasoning = analysis.get("reasoning", "")

            # 1. Video Similarity Override — force REJECT if below 0.95, REVIEW if below 0.98
            video_sim = self._last_metrics.get("overall_similarity", 1.0)
            if video_sim < 0.95 and analysis["verdict"] != "reject":
                analysis["verdict"] = "reject"
                analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Zgodność wideo ({video_sim:.2%}) jest poniżej krytycznego progu 95%. Wymuszono status REJECT. [Oryginalna notatka AI: {current_reasoning}]"
                current_reasoning = analysis["reasoning"]
            elif video_sim < 0.98 and analysis["verdict"] == "approve":
                analysis["verdict"] = "review"
                analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Zgodność wideo ({video_sim:.2%}) jest poniżej progu 98%. Wymuszono status REVIEW. [Oryginalna notatka AI: {current_reasoning}]"
                current_reasoning = analysis["reasoning"]

            # 2. Check STT condition early for LUFS override exception
            stt_data = self._last_metrics.get("audio_transcription", {})
            stt_skipped = self._last_metrics.get("stt_skipped", False)
            is_stt_ok = False
            if stt_skipped:
                is_stt_ok = True
            elif isinstance(stt_data, dict):
                if stt_data.get("is_text_match") is True:
                    is_stt_ok = True
                else:
                    stt_comp = self._last_metrics.get("audio_analysis_data", {}).get("speech_to_text", {}).get("comparison", {})
                    if isinstance(stt_comp, dict) and stt_comp.get("word_count_a", -1) == 0 and stt_comp.get("word_count_b", -1) == 0:
                        is_stt_ok = True

            # 3. LUFS Override — force REJECT if diff > 2.0, REVIEW if diff > 1.0
            audio_loudness = self._last_metrics.get("audio_loudness", {})
            if isinstance(audio_loudness, dict):
                lufs_diff = audio_loudness.get("lufs_difference")
                if lufs_diff is not None:
                    abs_lufs = abs(float(lufs_diff))

                    video_sim_lufs_check = self._last_metrics.get("overall_similarity", 1.0)
                    is_lufs_exception = (video_sim_lufs_check >= 0.98 and is_stt_ok)

                    if abs_lufs > 1.0 and is_lufs_exception:
                        logger.info(f"🔊 Ignorowanie różnicy LUFS ({lufs_diff}) ze względu na pełną zgodność Video i VO.")
                        # LLM should have already output APPROVE based on prompt, but just in case:
                        if analysis["verdict"] == "reject" or analysis["verdict"] == "review":
                            analysis["verdict"] = "approve"
                            analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Zignorowano różnicę głośności ({lufs_diff} LUFS), ponieważ obraz i lektor (VO) w pełni się zgadzają. Wymuszono status APPROVE. [Oryginalna notatka: {current_reasoning}]"
                            current_reasoning = analysis["reasoning"]
                    else:
                        if abs_lufs > 2.0 and analysis["verdict"] != "reject":
                            analysis["verdict"] = "reject"
                            analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Różnica głośności ({lufs_diff} LUFS) przekracza próg krytyczny 2.0. Wymuszono status REJECT. [Oryginalna notatka: {current_reasoning}]"
                            current_reasoning = analysis["reasoning"]
                        elif abs_lufs > 1.0 and analysis["verdict"] == "approve":
                            analysis["verdict"] = "review"
                            analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Różnica głośności ({lufs_diff} LUFS) przekracza dopuszczalny próg 1.0. Wymuszono status REVIEW. [Oryginalna notatka: {current_reasoning}]"
                            current_reasoning = analysis["reasoning"]

            # 4. Audio Similarity Override — reduce false-positives
            audio_sim_val = self._last_metrics.get("audio_similarity")
            if audio_sim_val is not None and not is_missing_audio:
                audio_sim_val = float(audio_sim_val)
                
                # Check Loudness condition
                audio_loudness = self._last_metrics.get("audio_loudness", {})
                is_loudness_ok = not (audio_loudness.get("has_loudness_issue", False) if isinstance(audio_loudness, dict) else False)
                
                has_green_flags = is_stt_ok and is_loudness_ok
                
                if has_green_flags:
                    threshold = 0.75
                    condition_str = "mimo zgodności STT i Loudness"
                else:
                    threshold = 0.90
                    condition_str = "przy braku pełnej zgodności STT/Loudness"
                    
                if audio_sim_val < threshold and analysis["verdict"] == "approve":
                    analysis["verdict"] = "review"
                    analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Zgodność audio (spektralna {audio_sim_val:.4f}) spadła poniżej progu {threshold} ({condition_str}). Wymuszono status REVIEW. [Oryginalna notatka: {current_reasoning}]"
                    current_reasoning = analysis["reasoning"]

            # 4. Duration Difference Override (Enforce REJECT if length differs > 0.5s and not ARPP)
            duration_diff = self._last_metrics.get("duration_difference", 0.0)
            is_arpp = self._last_metrics.get("is_arpp_slate", False)
            if duration_diff > 0.5 and not is_arpp and analysis["verdict"] != "reject":
                analysis["verdict"] = "reject"
                analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Pliki różnią się długością o {duration_diff:.1f}s i nie jest to format z planszami. Wymuszono status REJECT. [Oryginalna notatka: {analysis.get('reasoning', '')}]"
                current_reasoning = analysis["reasoning"]

            # 5. STT (Voice Over) Similarity Override — force REJECT if < 0.90
            if not is_missing_audio and not is_stt_ok:
                if isinstance(stt_data, dict):
                    text_sim = stt_data.get("text_similarity")
                    if text_sim is not None and float(text_sim) < 0.90:
                        if analysis["verdict"] != "reject":
                            analysis["verdict"] = "reject"
                            analysis["reasoning"] = f"🚨 SYSTEM OVERRIDE: Treść lektora (VO) wykazuje krytyczne różnice (zgodność tekstu {float(text_sim):.2%}). Wymuszono status REJECT. [Oryginalna notatka: {current_reasoning}]"
                            current_reasoning = analysis["reasoning"]

            confidence = analysis.get("confidence", 0.5)
            kb_used = analysis.get("kb_used", False)
            logger.info(
                f"✅ AI verdict: {verdict} | confidence: {confidence} | KB used: {kb_used}"
            )
            return analysis

        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.warning(
                f"⚠️ JSON parse failed ({e}). Trying regex fallback on free text..."
            )

            # ── Regex fallback: extract verdict keyword from prose ───────────────
            # Model sometimes writes e.g. "verdict is REJECT" or "I verdict: approve"
            verdict_match = re.search(
                r'\b(approve|reject|review)\b',
                raw_content,
                re.IGNORECASE
            )
            if verdict_match:
                extracted_verdict = verdict_match.group(1).lower()
                # Extract a reasonable reasoning snippet (first 2 sentences)
                sentences = re.split(r'(?<=[.!?])\s+', raw_content.strip())
                reasoning_snippet = " ".join(sentences[:2])[:300]
                logger.warning(
                    f"⚠️ Regex fallback extracted verdict='{extracted_verdict}' from prose"
                )
                return {
                    "verdict": extracted_verdict,
                    "reasoning": reasoning_snippet or raw_content[:200],
                    "confidence": 0.4,   # Lower confidence — we’re guessing from prose
                    "kb_used": False,
                }

            # ── Total failure: log and return REVIEW ────────────────────────
            logger.error(
                f"❌ Failed to parse AI response — no JSON and no verdict keyword found.\n"
                f"Raw content (first 300 chars): {raw_content[:300]}"
            )
            return {
                "verdict": "review",
                "reasoning": (
                    "Werdykt AI wymaga ręcznego sprawdzenia — model zwrócił odpowiedź "
                    "w niezrozumiałym formacie. Sprawdź logi backendu."
                ),
                "confidence": 0.0,
                "kb_used": False,
            }


def get_analyst() -> AnalystService:
    """Lazy loader for AnalystService singleton"""
    return AnalystService()
