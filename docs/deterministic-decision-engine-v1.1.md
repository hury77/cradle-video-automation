# Deterministic Decision Engine v1.1 — Specyfikacja zmian względem v1

Dokument opisuje zmiany wprowadzone w silniku deterministycznym (`DeterministicDecisionEngineV1`), adapterze metryk (`deterministic_metrics_adapter.py`) oraz potoku analizy (`comparison_service.py` / `analyst_service.py`) w stosunku do pierwotnej specyfikacji v1 (`docs/deterministic-decision-engine-v1.md`).

---

## 1. Identyczna para plików (`DUPLICATE_INPUT`) jako poprawny workflow Cradle

W Cradle dozwolonym i częstym scenariuszem biznesowym jest workflow **„załącz ostatni plik”**, w którym plik akceptu i plik emisji są binarnie identyczne (`is_binary_duplicate == True`).

- **Zmiana w pipeline (`comparison_service.py`, `analyst_service.py`):**
  - Wykrycie identyczności binarnej (`is_binary_duplicate`) pozostaje w metrykach jako flaga informacyjna, ale nie wymusza `REVIEW`.
  - Wykonywana jest normalna analiza audio (`compare_loudness`, `compare_audio_similarity`, `compare_audio_files`) — dzięki temu panel szczegółów audio w UI otrzymuje pełne dane głośności i spektralne.
  - Pomijane jest wyłącznie ciężkie STT (Demucs + Whisper), a `speech_to_text` otrzymuje `status="skipped"`, `skipped_reason="DUPLICATE_INPUT: Acceptance and Emission are binary identical files (Cradle workflow: attach last file)"`, `is_uncertain=False`.
- **Warunki `RULE_QUALIFIED_APPROVE` dla identycznej pary w silniku:**
  - `is_binary_duplicate is True` oraz `stt_status == "skipped"` z kanonicznym kodem `DUPLICATE_INPUT` po ścisłej normalizacji (`normalize_skip_code_strict`),
  - `video_similarity >= 0.98`,
  - `duration_difference <= 0.5 s` (lub zweryfikowana plansza `is_arpp_slate is True`),
  - `audio_probe_complete is True` i `audio_mismatch is False`,
  - przy obecnym audio: `audio_similarity >= 0.98` (wyższy próg niż standardowe `0.75`),
  - brak obcej flagi niepewności (`is_uncertain is False`, z dopuszczeniem historycznego `uncertainty_reason` normalizującego się do `DUPLICATE_INPUT`),
  - wartość `lufs_difference = None` jest dopuszczalna wyłącznie w tym scenariuszu.
  - Powód w uzasadnieniu: `"Pliki akceptu i emisji są identyczne (workflow Cradle: załącz ostatni plik)"`.

---

## 2. Minimalna długość mowy dla twardego `REJECT` za niezgodność tekstu

- Dodano stałą `MIN_WORDS_FOR_TEXT_REJECT = 5` w `deterministic_decision_engine.py`.
- `RULE_HARD_REJECT` za rozbieżność transkrypcji (`text_similarity < 0.90`) może zostać wydany **wyłącznie wtedy, gdy OBA transkrypty mają co najmniej 5 słów** (`word_count_a >= 5 and word_count_b >= 5`).
- Gdy `stt_status == "completed"`, `not is_text_match`, a którykolwiek transkrypt ma `< 5` słów (np. halucynacje Whispera na tle muzycznym lub asymetria 0 vs 6 słów), silnik wydaje `RULE_PROTECTIVE_REVIEW` z powodem `"zbyt krótki transkrypt do wiarygodnej oceny zgodności lektora"` (bez cytowania treści).

---

## 3. Weryfikacja „brak mowy” (`completed_no_speech`) w trybie `AUTOMATION`

- W trybie `AUTOMATION` proporcja muzyki (`music_proportion` / `music_dominant`) nie jest wyliczana (`None`), co w v1 blokowało kontrakt (`has_raw_vad_complete=False`).
- W `deterministic_metrics_adapter.py` i `is_verified_no_speech_result()` (`deterministic_decision_engine.py`):
  - Dla `comparison_type == "automation"` dopuszczono `music_dominant in (False, None)` (przy `music_dominant is True` nadal wymagany jest `REVIEW`).
  - Dla trybu `FULL` (oraz braku typu `automation`) zachowano ścisły wymóg `music_dominant is False`.
  - Zachowano wszystkie pozostałe warunki: `stt_status == "completed_no_speech"` (lub legacy `completed` z pustym tekstem), `word_count_a == 0` i `word_count_b == 0`, `is_uncertain is False`, `audio_mismatch is False`, `is_binary_duplicate is False`, `raw_vad_metrics_complete is True`, `raw_vad_error in (False, None)`, `raw_vad_inconclusive is False`, `raw_vad_speech is False`, `raw_vad_status_acc == "no_speech"`, `raw_vad_status_emi == "no_speech"`, `raw_vad_speech_acc is False`, `raw_vad_speech_emi is False`, poprawny `lufs_difference` (`|LUFS| <= 3.0 dB`) oraz `audio_similarity >= 0.75`.
  - Wykrycie mowy po jednej stronie lub jakakolwiek asymetria nadal kieruje job do `REVIEW`.

---

## 4. Uzasadnienie progu `|LUFS| <= 3.0 dB` (`REVIEW` zamiast `REJECT`)

- W dostępnych zapisach (`4` wpisy w KB wskazujące specyfikację eksportu dla `2` klientów oraz `3` nadpisania `human` w batchu ewaluacyjnym 1) powodem zatwierdzenia przy różnicy `|lufs_difference| > 2.0 dB` było dostosowanie głośności do specyfikacji emisyjnej.
- Przyjęcie progu tolerancji `<= 3.0 dB` dla `APPROVE` oraz kierowanie przekroczeń `> 3.0 dB` do `RULE_PROTECTIVE_REVIEW` (zamiast twardego `REJECT`) ogranicza fałszywe odrzucenia przy różnicach specyfikacji eksportu, zachowując eskalację do człowieka przy większych odchyleniach.

---

## 5. Obsługa ciszy w audio (`both_silent` i `one_side_silent`)

- W `compare_loudness` (`new_video_compare/backend/services/audio_service.py`) wartości `integrated_lufs` równe `None`, `-inf` lub `NaN` są bezpiecznie klasyfikowane jako cisza (bez wyjątku formatowania `NoneType.__format__` w logach):
  - **`both_silent = True`** (obie ścieżki ciche): `lufs_difference = 0.0`, `is_lufs_match = True`, `is_peak_match = True`, `has_loudness_differences = False`, brak klucza `"error"`. Przy `audio_similarity >= 0.98` (i spełnieniu pozostałych warunków) nie blokuje `APPROVE`.
  - **`one_side_silent = True`** (jedna ścieżka cicha, druga z sygnałem): `lufs_difference = None`, `is_lufs_match = False`, brak klucza `"error"`. Adapter (`deterministic_metrics_adapter.py`) uznaje `has_lufs = True` dla kompletności kontraktu, a silnik (`deterministic_decision_engine.py`, sekcja `B7`) wymusza `RULE_PROTECTIVE_REVIEW` z powodem zawierającym `"Asymetria ciszy"`.

---

## 6. Progi głośności w systemie

| Próg | Lokalizacja w kodzie | Rola |
|---|---|---|
| `1.0 LU` | `new_video_compare/backend/services/audio_service.py` (linia `523`, `lufs_tolerance = 1.0`) | Pomiar w `compare_loudness`, flagi `is_lufs_match` / `has_loudness_differences` (badge ostrzegawczy w UI) |
| `2.0 LU` | `new_video_compare/backend/services/analyst_service.py` (linia `641`, `abs_lufs > 2.0`) | Twardy `SYSTEM OVERRIDE` w `AnalystService` wymuszający `REJECT` (tymczasowy — do usunięcia po przełączeniu na silnik deterministyczny) |
| `3.0 dB` | `new_video_compare/backend/services/deterministic_decision_engine.py` (linia `756`, `abs_lufs_diff > 3.0`) | Silnik deterministyczny (`DeterministicDecisionEngineV1`): `RULE_PROTECTIVE_REVIEW` powyżej `3.0 dB` |

---

## 7. Baza Wiedzy (KB) i `whisper_hallucinations`

- `AnalystService._load_knowledge_context` (`new_video_compare/backend/services/analyst_service.py`, linie `101–172`) wstrzykuje historię decyzji z `qa_decisions` wyłącznie jako kontekst few-shot do promptu LLM (maksymalnie `5` decyzji `human` + `3` decyzje `agent` per klient); w kodzie istnieje `0` reguł deterministycznych sterowanych przez KB.
- Tabela `whisper_hallucinations` (`25` wpisów) działa w warstwie filtrowania transkrypcji STT niezależnie od agenta i pozostaje aktywna bez zmian.

---

## 8. Raw VAD liczony także w `AUTOMATION` dla `completed_no_speech`

- Wydzielono helper `_populate_raw_vad_metrics(audio_result, acceptance_path, emission_path)` w `comparison_service.py`.
- W trybie `FULL` zachowano wywołanie przed bramką STT (jak w v1).
- W trybie `AUTOMATION` helper wywoływany jest po STT, gdy `audio_pair_comparable` jest `True`, `speech_to_text.status == "completed_no_speech"` i `raw_vad_metrics_complete` nie zostało jeszcze ustawione — bez wpływu na `AnalystService` i z minimalnym narzutem CPU (~0.2–0.8 s, poza pamięcią MPS).

---

## 9. Zestawienie progów i stałych w kodzie

| Parametr / Stała | Wartość w kodzie | Znaczenie / Reguła |
|---|---|---|
| `MIN_WORDS_FOR_TEXT_REJECT` | `5` | Minimum słów w obu transkryptach wymagane do `RULE_HARD_REJECT` |
| Próg `video_similarity` (REJECT) | `< 0.95` | Poniżej 95% → `RULE_HARD_REJECT` |
| Próg `video_similarity` (REVIEW / APPROVE) | `0.95 <= x < 0.98` / `>= 0.98` | Strefa graniczna → `REVIEW`; `>= 98%` → `APPROVE` |
| Próg `duration_difference` | `> 0.5 s` | Bez `is_arpp_slate=True` → `RULE_HARD_REJECT` |
| Próg `|lufs_difference|` | `<= 3.0 dB` | Powyżej `3.0 dB` (przy porównywalnym audio) → `RULE_PROTECTIVE_REVIEW` |
| Próg `audio_similarity` (standard) | `>= 0.75` | Poniżej `0.75` → `RULE_PROTECTIVE_REVIEW` |
| Próg `audio_similarity` (identyczna para / fast-path) | `>= 0.98` | Wymagane dla `verified_duplicate_pair` i `FAST_PATH_IDENTICAL_AUDIO` |
| Próg `text_similarity` (REJECT / REVIEW) | `< 0.90` / `0.90 <= x < 1.0` | `< 90%` (przy `>= 5` słowach) → `REJECT`; `90–99.9%` → `REVIEW` |
| Próg `music_proportion` (`music_dominant`) | `> 0.55` | Dominacja muzyki wyzwalająca STT w `FULL` i blokująca `no_speech` |
| `CANONICAL_DUPLICATE_INPUT` | `"DUPLICATE_INPUT"` | Kanoniczny kod skipu dla identycznej pary |
| `CANONICAL_FAST_PATH_IDENTICAL_AUDIO` | `"FAST_PATH_IDENTICAL_AUDIO"` | Kanoniczny kod skipu fast-path |
| `CANONICAL_FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH` | `"FULL_MODE_IDENTICAL_LOUDNESS_AND_NO_SPEECH"` | Kanoniczny kod skipu w trybie `FULL` |
| `CANONICAL_NO_AUDIO_STREAMS` | `"NO_AUDIO_STREAMS"` | Kanoniczny kod skipu dla par niemych (DOOH) |

---

## 10. Tryb główny (`DECISION_ENGINE`)

- **Flaga konfiguracyjna:** `settings.decision_engine` (zmienna środowiskowa `DECISION_ENGINE` w `new_video_compare/backend/config.py`).
  - Dozwolone wartości: `"agent"` (domyślna) oraz `"deterministic_rules_v1"`.
  - Każda niepoprawna wartość powoduje ostrzeżenie w logu i bezpieczny powrót do `"agent"`.
- **Zachowanie w trybie `"agent"` (domyślny):**
  - Pełna zgodność wsteczna: `ComparisonService._run_ai_analyst` wywołuje `AnalystService` (Ollama), stosuje nadpisania STT, zapisuje `decided_by="agent"` oraz (gdy `DETERMINISTIC_SHADOW_MODE=true`) wykonuje ocenę shadow do `knowledge_snapshot["deterministic_shadow_v1"]`.
- **Zachowanie w trybie `"deterministic_rules_v1"`:**
  - `main.lifespan` pomija sprawdzanie i automatyczne uruchamianie procesu Ollama.
  - `ComparisonService._run_ai_analyst` nie wywołuje `get_analyst().analyze_job_results` (Ollama nie jest używana).
  - Metryki są adaptowane przez `adapt_comparison_metrics(metrics, job_meta=...)` (z `comparison_type`) i walidowane przez `is_metrics_contract_complete`:
    - niekompletny kontrakt → `REVIEW` (`status="insufficient_metrics"`, `failed_flags`),
    - wyjątek silnika → `REVIEW` z zanonimizowanym komunikatem (`redact_shadow_error`, `status="error"`),
    - kompletny kontrakt → `DeterministicDecisionEngineV1().evaluate(canonical)`.
  - Decyzja zapisywana jest w `qa_decisions` z `decided_by="deterministic_rules_v1"`, a zredagowany ślad reguł trafia do `knowledge_snapshot["deterministic_decision_v1"]` (bez klucza `deterministic_shadow_v1`).
  - UI (`QAVerdictPanel.tsx`) wyświetla osobną etykietę (`Deterministic Rules Engine v1 — automatic decision`) i obsługuje nadpisanie przez człowieka (`decided_by="human"` + `override_reason`).
- **Rollback:** zmiana `DECISION_ENGINE=agent` w `.env` i restart backendu natychmiast przywraca ścieżkę agenta AI bez migracji bazy danych.

---

## 11. Usunięcie Ollamy

- **Data:** `2026-11-25`
- **Tag powrotu:** `pre-ollama-removal-2af4f4f` (na `2af4f4f`, wypchnięty do `origin`).
- **Zakres zmian:**
  - Usunięto `new_video_compare/backend/services/analyst_service.py`, `scripts/test_analyst.py`, `scripts/test_soul_rigour.py` oraz zależność `ollama==0.4.5` z `requirements.txt`.
  - `main.py` (`lifespan`) nie sprawdza ani nie uruchamia procesu Ollama; `comparison_service._run_ai_analyst` zawsze wykonuje ścieżkę deterministyczną (`_run_deterministic_primary`).
  - `SOUL.md` przeniesiono do `docs/legacy/SOUL.md` jako dokumentację historyczną.
  - Pola `decision_engine` i `deterministic_shadow_mode` w `config.py` pozostają jako przestarzałe (żeby istniejące pliki `.env` nie powodowały błędów walidacji); wartość inna niż `"deterministic_rules_v1"` loguje ostrzeżenie `"agent removed"`.
  - Historyczne rekordy w bazie (`decided_by="agent"`, `deterministic_shadow_v1`) nie są migrowane; UI zachowuje odznakę historyczną.
- **Skutki:** brak trybu `agent` oraz brak wstrzykiwania przykładów few-shot z KB do promptu LLM.
- **Pozostałe mechanizmy:** tabela `whisper_hallucinations` (`25` wpisów) pozostaje aktywna w warstwie filtrowania STT.

---

## 12. Szew doradczy (`DecisionAdvisor`)

- Moduł `new_video_compare/backend/services/decision_advisor.py` definiuje protokół `DecisionAdvisor` (`annotate(canonical_metrics, decision) -> Optional[dict]`) oraz domyślną implementację `NullAdvisor` (`ADVISOR_PROVIDER=none`, jedyna dozwolona wartość).
- **Zasady dopinania ewentualnego modelu w przyszłości:**
  1. **Wyłącznie doradczo:** wynik trafia wyłącznie do `knowledge_snapshot["advisor_v1"]` dla celów audytu; **werdykt (`verdict`) oraz `decided_by` nigdy nie mogą być zmienione przez advisora**.
  2. **Brak automatycznego `APPROVE`:** advisor nie może wydawać ani nadpisywać zatwierdzeń.
  3. **Izolacja i timeout:** wywołanie działa w `try/except` z krótkim limitem czasu; błąd lub timeout nie wpływa na decyzję.
  4. **Wymagana zgoda bezpieczeństwa:** podłączenie dowolnego modelu wymaga osobnej weryfikacji bezpieczeństwa i aktualizacji dozwolonych wartości `ADVISOR_PROVIDER`.
