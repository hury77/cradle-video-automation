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

## 3. Testy Regresyjne
Aby zapobiec wycofaniu lub nadpisaniu poprawek w przyszłości, wdrożono test automatyczny.
- **Plik**: `backend/tests/test_audio_mismatch_regression.py`
- **Wynik**: W pełni przechodzi (2 passed) potwierdzając zachowanie zarówno bloku bez kar (DOOH) jak i rygorystycznego wariantu mismatch (kara w similarity i krytyczny prompt).

## 4. Punkty Otwarte / Do dalszej weryfikacji
Choć logika wewnątrz modułów jest spójna i bezbłędna, do ostatecznego odhaczenia całego pionu pozostają dwa punkty z testów End-to-End:
1. **Realny test E2E**: Uruchomienie `ComparisonService` na w pełni realnym pliku bez audio i pliku udającym mismatch (np. przy użyciu ffmpeg z modyfikatorem `-an` w normalnym środowisku roboczym).
2. **Potwierdzenie w UI**: Upewnienie się na pełnych danych z bazy `sqlite`, że marker **CRITICAL** i napis **"Błąd: Brak audio w jednym z plików"** rzeczywiście pojawia się w odpowiednim oknie na froncie Difference Inspector (bez polegania jedynie na mockowanych obiektach w unit testach).
