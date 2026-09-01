# Raport Weryfikacji: Naprawa DOOH (Audio Null Constraint)

## 1. Podsumowanie Problemu
W poprzednich wersjach pliki pozbawione ścieżki dźwiękowej (takie jak animacje DOOH) powodowały błąd `IntegrityError: NOT NULL constraint failed` w tabeli bazy danych dla pola `similarity_score`. Zamiast przetwarzać je jako materiały w 100% zgodne merytorycznie (oba nieme), system wyrzucał błąd i oznaczał Job statusem `FAILED`. 

Wprowadzono system tzw. "Sentinel Values" omijających ten błąd po stronie zapisu bazy:
- `similarity_score = 1.0` dla plików, gdzie oba są nieme (no_audio_tracks).
- `similarity_score = 0.0` dla przypadku *mismatch* (jedno wideo z audio, drugie bez).

## 2. Zidentyfikowane i Naprawione Bugi
W trakcie weryfikacji wykryto i załatano dwa krytyczne błędy logiczne, które niwelowały skuteczność sentinel values:
- **Brak kary w `overall_similarity` za mismatch (comparison_service.py)**: Stary kod pomijał jakiekolwiek kary dla finalnego wyniku dopasowania w przypadku `has_audio is False`, obsługując nim zarówno pliki naturalnie nieme jak i rozbieżne. Zostało to naprawione. Mismatch radykalnie i bezwzględnie redukuje teraz `overall_similarity` do `0.0`.
- **Łagodny komunikat w AI (AnalystService)**: Model regułowy `_generate_rule_based_reasoning` zgłaszał ten sam, łagodny komunikat o "niemej naturze pliku" w obu przypadkach. Po łatce rozróżnia je precyzyjnie. 
  - W przypadku DOOH raportuje: "brak ścieżki dźwiękowej w materiałach (plik niemy / GIF)".
  - W przypadku mismatchu alarmuje: "KRYTYCZNA RÓŻNICA — brak ścieżki dźwiękowej w jednym z plików (mismatch)".

- **Nadpisywanie `overall_similarity` przez `video_similarity` (comparison_service.py)**: Metoda `_run_ai_analyst` błędnie nadpisywała prawdziwe zredukowane za audio mismatch `overall_similarity` wartością `video_similarity` przed wysłaniem do LLM, przez co detekcja anomalii ulegała zamaskowaniu. Zostało to załatane.

## 3. Decyzje Biznesowe (Verdict: REVIEW)
Zgodnie z weryfikacją, w przypadku mismatchu w ścieżce dźwiękowej werdykt wymuszany przez system to **REVIEW**, a nie REJECT. 
- **Uzasadnienie**: Mismatch audio jest traktowany jako krytyczna uwaga, ale wymusza ostateczną ręczną weryfikację. Uznano to za spójne z obsługą wszystkich anomalii dźwiękowych (jedynie błędy czysto tekstowe typu <0.90 dają bezwzględny REJECT). 

## 4. Testy Regresyjne
Aby zapobiec wycofaniu lub nadpisaniu poprawek w przyszłości, wdrożono i zaktualizowano testy automatyczne:
- **Plik**: `backend/tests/test_audio_mismatch_regression.py`
- **Wynik**: W pełni przechodzi (2 passed) potwierdzając zachowanie zarówno bloku bez kar (DOOH) jak i rygorystycznego wariantu mismatch (kara w similarity i wymuszenie REVIEW).

## 5. Wyniki Testu E2E
Przeprowadzono pełny, natywny test End-to-End na realnym pliku (wygenerowano wyciszoną kopię przy pomocy ffmpeg z opcją `-an`). 
- **Werdykt w SQLite**: Zapisany jako `REVIEW`.
- **Reasoning**: Prawidłowo dołączono i wyegzekwowano prefiks: `🚨 SYSTEM OVERRIDE: KRYTYCZNA RÓŻNICA — brak ścieżki dźwiękowej w jednym z plików (mismatch). Wymuszono status REVIEW.`

Punkty otwarte zostały tym samym zrealizowane i cały przepływ dla plików DOOH i problemów z mismatch audio jest stabilny.
