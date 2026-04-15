# Ustawienia Czułości Systemu QA (SENSITIVITY_THRESHOLDS)

Plik konfiguracyjny: [backend/config.py](./new_video_compare/backend/config.py)

System New Video Compare posiada cztery zdefiniowane poziomy czułości, które wpływają na progi akceptacji różnic w wideo oraz sposób przetwarzania dźwięku.

## 1. Poziom Niski (`low`)
*   **Minimalny SSIM**: `0.85` (Podstawowe podobieństwo strukturalne)
*   **Tolerancja pikseli**: `10%` (Dopuszczalna różnica w klatkach)
*   **Normalizacja jakości**: Nie
*   **Zastosowanie**: Szybka weryfikacja techniczna przy dużej tolerancji na zmiany.

## 2. Poziom Średni (`medium`)
*   *Poziom domyślny*
*   **Minimalny SSIM**: `0.93` (Podniesione z 0.92 dla lepszej detekcji tekstu)
*   **Tolerancja pikseli**: `4%` (Zmniejszone z 5%)
*   **Normalizacja jakości**: Nie
*   **Zastosowanie**: Optymalny balans między dokładnością a szybkością. Standardowy tryb pracy.

## 3. Poziom Wysoki (`high`)
*   **Minimalny SSIM**: `0.94` (Rygorystyczne, ignoruje drobne różnice kodeków)
*   **Tolerancja pikseli**: `1.5%` (Hard-pixel — łapie przesunięcia tekstu pominięte przez globalny SSIM)
*   **Normalizacja jakości**: Tak (Wyrównywanie jakości przed porównaniem)
*   **Audio (Demucs)**: Włączone (Separacja lektora i porównanie głosowe)
*   **Audio (Whisper)**: Tak (Pełna transkrypcja i porównanie tekstu)
*   **Detekcja hybrydowa**: Tak — klatka flagowana jeśli SSIM < próg **LUB** diff_ratio > tolerancja pikseli
*   **Zastosowanie**: Krytyczne sprawdzenie przed emisją. Wymaga niemal identycznego dopasowania.

## 4. Poziom Automatyzacji (`automation`)
*   **Minimalny SSIM**: `0.95` (Zbalansowane — 0.98 powodowało fałszywe alarmy z kompresji)
*   **Tolerancja pikseli**: `0.5%` (Hard-pixel — wykrywa najdrobniejsze przesunięcia napisów bez reagowania na szum kompresji)
*   **Normalizacja jakości**: Tak
*   **Audio (Demucs)**: Tak
*   **Audio (Whisper)**: Tak (Pełna transkrypcja i porównanie tekstu)
*   **Detekcja hybrydowa**: Tak — klatka flagowana jeśli SSIM < próg **LUB** diff_ratio > tolerancja pikseli
*   **Próg szumu**: `30/255` — różnice poniżej tego progu (artefakty kompresji mp4/mov) są ignorowane
*   **Zastosowanie**: Tryb pracy agentów autonomicznych (Controller/Analyst). Przesunięcia tekstu i lokalne zmiany wykrywane precyzyjnie bez fałszywych alarmów.

---
*Ostatnia aktualizacja: 2026-04-15*
