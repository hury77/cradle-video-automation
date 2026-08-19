# Ustawienia Czułości Systemu QA (SENSITIVITY_THRESHOLDS)

Plik konfiguracyjny: [backend/config.py](./new_video_compare/backend/config.py) oraz definicje FPS i limitów klatek w [backend/services/comparison_service.py](./new_video_compare/backend/services/comparison_service.py)

System New Video Compare posiada cztery zdefiniowane poziomy czułości, które wpływają na progi akceptacji różnic w wideo, gęstość próbkowania (klatki na sekundę) oraz sposób przetwarzania dźwięku.

## 1. Poziom Niski (`low`)
*   **Minimalny SSIM**: `0.93` (Podstawowe podobieństwo strukturalne, zbliżone do trybu High)
*   **Tolerancja pikseli**: `1.5%` (Dopuszczalna różnica w klatkach, niewielka tolerancja na kompresję)
*   **Częstotliwość analizy**: `3.0 klatki/s` (FPS - zbalansowana precyzja czasowa)
*   **Maksymalna liczba klatek**: `1800` (Ok. 10 minut wideo przy 3.0 klatki/s)
*   **Normalizacja jakości**: Tak
*   **Audio (Demucs)**: Tak (Separacja lektora włączona)
*   **Audio (Whisper)**: Tak (Pełna transkrypcja włączona)
*   **Zastosowanie**: Szybka weryfikacja techniczna przy nieznacznie podwyższonej tolerancji na zmiany kompresyjne względem High.

## 2. Poziom Średni (`medium`)
*   *Poziom domyślny*
*   **Minimalny SSIM**: `0.93` (Podniesione z 0.92 dla lepszej detekcji tekstu)
*   **Tolerancja pikseli**: `4%` (Zmniejszone z 5% - dopuszczalny ułamek różnych pikseli)
*   **Częstotliwość analizy**: `2.0 klatki/s` (FPS)
*   **Maksymalna liczba klatek**: `900` (Ok. 7.5 minuty wideo przy 2.0 klatki/s)
*   **Normalizacja jakości**: Nie
*   **Zastosowanie**: Optymalny balans między dokładnością a szybkością. Standardowy tryb pracy.

## 3. Poziom Wysoki (`high`)
*   **Minimalny SSIM**: `0.95` (Zbalansowane — 0.98 powodowało fałszywe alarmy z kompresji; dopasowane do trybu automatyzacji)
*   **Tolerancja pikseli**: `0.5%` (Hard-pixel — wykrywa najdrobniejsze przesunięcia napisów bez reagowania na szum kompresji; dopasowane do trybu automatyzacji)
*   **Częstotliwość analizy**: `5.0 klatek/s` (FPS - wysoka gęstość próbkowania dla dokładnego wykrywania krótkich zmian)
*   **Maksymalna liczba klatek**: `3000` (Ok. 10 minut wideo przy 5.0 klatkach/s)
*   **Normalizacja jakości**: Tak (Wyrównywanie jakości przed porównaniem)
*   **Audio (Demucs)**: Włączone (Separacja lektora i porównanie głosowe)
*   **Audio (Whisper)**: Tak (Pełna transkrypcja i porównanie tekstu)
*   **Detekcja hybrydowa**: Tak — klatka flagowana jeśli SSIM < próg **LUB** diff_ratio > tolerancja pikseli
*   **Zastosowanie**: Krytyczne sprawdzenie przed emisją. Wymaga niemal identycznego dopasowania.

## 4. Poziom Automatyzacji (`automation`)
*   **Minimalny SSIM**: `0.95` (Zbalansowane — 0.98 powodowało fałszywe alarmy z kompresji)
*   **Tolerancja pikseli**: `0.5%` (Hard-pixel — wykrywa najdrobniejsze przesunięcia napisów bez reagowania na szum kompresji)
*   **Częstotliwość analizy**: `5.0 klatek/s` (FPS - maksymalna dokładność)
*   **Maksymalna liczba klatek**: `3000` (Ok. 10 minut wideo przy 5.0 klatkach/s)
*   **Normalizacja jakości**: Tak
*   **Audio (Demucs)**: Tak
*   **Audio (Whisper)**: Tak (Pełna transkrypcja i porównanie tekstu)
*   **Detekcja hybrydowa**: Tak — klatka flagowana jeśli SSIM < próg **LUB** diff_ratio > tolerancja pikseli
*   **Próg szumu**: `30/255` — różnice poniżej tego progu (artefakty kompresji mp4/mov) są ignorowane w detekcji pikselowej
*   **Zastosowanie**: Tryb pracy agentów autonomicznych (Controller/Analyst). Przesunięcia tekstu i lokalne zmiany wykrywane precyzyjnie bez fałszywych alarmów.

## 5. Progi Decyzyjne Warstwy Audio/Tekstu (AnalystService)

Progi te są egzekwowane deterministycznie przez system (nadpisując ewentualne halucynacje LLM) w pliku [backend/services/analyst_service.py](./new_video_compare/backend/services/analyst_service.py) (sekcja *Deterministic Threshold Enforcers*). Zostały one skalibrowane na podstawie realnych decyzji QA w środowisku produkcyjnym i mogą ulegać adaptacji.

### A. Audio Spectral/MFCC Similarity (`overall_audio_similarity`)
* **Guard nigdy nie wymusza REJECT** — maksymalna reakcja to wymuszony `REVIEW`.
* Jeśli `stt_is_match = true` (lub `stt_skipped = true`) **ORAZ** `has_loudness_issue = false` → próg interwencji: **`< 0.75`** → wymuszony `REVIEW`.
* W pozostałych przypadkach → próg interwencji: **`< 0.90`** → wymuszony `REVIEW`.
* *Uzasadnienie*: Drobne różnice spektralne (inna kompresja/eksport) są nieszkodliwe, gdy tekst mówiony i głośność są w normie. Zostało to potwierdzone realną decyzją QA przy zadaniu (job 992), gdzie przy `audio_sim=0.88` i zachowanych zielonych flagach dla tekstu i głośności werdykt `APPROVE` musiał zostać zachowany.

### B. Text/VO Similarity (`text_similarity`)
* Jeśli `text_similarity < 0.90` → system **bezwzględnie wymusza REJECT**, niezależnie od werdyktu zaproponowanego przez LLM oraz niezależnie od idealnego `video_similarity`.
* *Uzasadnienie*: Drastyczna niezgodność językowa lub merytoryczna lektora (VO) to najpoważniejszy błąd, niepodlegający taryfie ulgowej. Potwierdzone błędem modelu w zadaniu (job 1056), gdzie włoski lektor został porównany z polską emisją (~5% zgodności tekstu), a LLM błędnie przydzielił pobłażliwy status `REVIEW` mimo drastycznej różnicy.

### C. Ważne rozróżnienie: Próg UI vs Progi decyzyjne
* Próg `similarity_score < 0.99` umieszczony w kodzie `comparison_service.py` generuje **wyłącznie wizualny marker** `AUDIO_SPECTRAL` na osi czasu w interfejsie użytkownika.
* Jest to próg czysto kosmetyczny. Jest całkowicie niezależny od twardych progów decyzyjnych A i B działających na poziomie Analityka (nie należy ich ze sobą mylić).

### D. Wymuszenie języka odpowiedzi
* Prompt systemowy dla LLM zawiera twardy nakaz tekstowy: uzasadnienie (reasoning) musi bezwzględnie zostać zwrócone **w języku polskim**.
* Warto zaznaczyć, że jest to instrukcja tekstowa przekazywana do modelu językowego (zabezpieczająca przed dryfowaniem w kierunku angielskiego), a nie twardy, deterministyczny guard w kodzie. Istnieje teoretyczna możliwość zignorowania tej reguły przez mniejsze modele, dlatego polegamy mocniej na rygorach A i B dla samych decyzji.

---
*Ostatnia aktualizacja: 2026-08-19*
