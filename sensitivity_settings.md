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

---
*Ostatnia aktualizacja: 2026-05-20*
