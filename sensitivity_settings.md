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
*   **Tolerancja pikseli**: `3%`
*   **Normalizacja jakości**: Tak (Wyrównywanie jakości przed porównaniem)
*   **Audio (Demucs)**: Włączone (Separacja lektora i porównanie głosowe)
*   **Audio (Whisper)**: Tak (Pełna transkrypcja i porównanie tekstu)
*   **Zastosowanie**: Krytyczne sprawdzenie przed emisją. Wymaga niemal identycznego dopasowania.

## 4. Poziom Automatyzacji (`automation`)
*   **Minimalny SSIM**: `0.98` (Ekstremalnie rygorystyczne)
*   **Tolerancja pikseli**: `1%`
*   **Normalizacja jakości**: Tak
*   **Audio (Demucs)**: Tak
*   **Audio (Whisper)**: Tak (Pełna transkrypcja i porównanie tekstu)
*   **Zastosowanie**: Tryb pracy agentów autonomicznych (Controller/Analyst). Każda zauważalna różnica zostanie zgłoszona do weryfikacji ludzkiej.

---
*Ostatnia aktualizacja: 2026-03-30*
