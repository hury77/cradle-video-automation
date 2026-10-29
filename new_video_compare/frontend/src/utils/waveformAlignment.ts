/**
 * utils/waveformAlignment.ts
 *
 * Logika obliczania stylów transformacji wizualnej dla Audio Waveform Comparison
 * w przypadku wystąpienia Clock / ARPP / Clearcast slate lub innego offsetu synchronizacji.
 */

export interface WaveformTimelineOffsets {
  acceptanceOffset: number; // sekundy
  emissionOffset: number;   // sekundy
  displayDuration: number;  // sekundy (wspólna widoczna długość contentu)
}

export interface WaveformTrackTransform {
  // Czy dla danej ścieżki zastosowano kompensację synchronizacji
  isAligned: boolean;
  // Przesunięcie w lewo w procentach kontenera (np. 33.333% dla 10s slate w 40s pliku z 30s contentem)
  leftPercent: number;
  // Szerokość elementu fali dźwiękowej w procentach kontenera (np. 133.333% dla pliku 40s w osi 30s)
  widthPercent: number;
  // Czy ścieżka ma pusty padding na początku (gdy plik zaczyna się później niż oś contentu)
  paddingLeftPercent: number;
  // Opis / etykieta tooltipu
  alignmentLabel: string | null;
}

export interface AudioWaveformAlignmentResult {
  hasActiveAlignment: boolean;
  acceptance: WaveformTrackTransform;
  emission: WaveformTrackTransform;
}

/**
 * Oblicza transformację wizualną dla obu waveformów, tak aby ich content
 * odpowiadał dokładnie osi czasu wspólnego playbacku (0..displayDuration).
 *
 * @param offsets Obliczone offsety i displayDuration z useMemo
 * @param accFileDuration Rzeczywisty czas trwania pliku acceptance (sekundy)
 * @param emiFileDuration Rzeczywisty czas trwania pliku emission (sekundy)
 */
export function calculateWaveformTransforms(
  offsets: Partial<WaveformTimelineOffsets> | null | undefined,
  accFileDuration: number = 0,
  emiFileDuration: number = 0
): AudioWaveformAlignmentResult {
  const defaultTransform = (isAligned: boolean = false, label: string | null = null): WaveformTrackTransform => ({
    isAligned,
    leftPercent: 0,
    widthPercent: 100,
    paddingLeftPercent: 0,
    alignmentLabel: label,
  });

  const rawAccOffset = Number(offsets?.acceptanceOffset) || 0;
  const rawEmiOffset = Number(offsets?.emissionOffset) || 0;
  const rawDisplayDuration = Number(offsets?.displayDuration) || 0;

  // Fail-safe: jeśli brak displayDuration lub oba offsety są równe 0, zwracamy 100% bez zmian
  if (rawDisplayDuration <= 0 || (rawAccOffset === 0 && rawEmiOffset === 0)) {
    return {
      hasActiveAlignment: false,
      acceptance: defaultTransform(false, null),
      emission: defaultTransform(false, null),
    };
  }

  const computeTrack = (
    offset: number,
    fileDuration: number,
    trackLabel: string
  ): WaveformTrackTransform => {
    // Jeśli offset dla danej ścieżki to 0, plik zaczyna się równo z czasem 0 contentu
    if (offset === 0) {
      // Jeśli plik ma taką samą długość jak displayDuration (lub krótszy), zajmuje 100% (lub proporcjonalnie)
      const ratio = fileDuration > 0 && rawDisplayDuration > 0
        ? (fileDuration / rawDisplayDuration) * 100
        : 100;
      return {
        isAligned: false,
        leftPercent: 0,
        widthPercent: Math.max(100, ratio),
        paddingLeftPercent: 0,
        alignmentLabel: null,
      };
    }

    // Offset dodatni oznacza, że początkowe `offset` sekund pliku to Clock / slate
    // Skoro użytkownik ogląda czas t od 0, punkt t=0 odpowiada t_file = offset.
    // Zatem szerokość całego pliku na osi czasu contentu to (fileDuration / displayDuration) * 100%.
    // Przesunięcie fali w lewo, aby czas `offset` trafił na lewą krawędź (x=0), to -(offset / displayDuration) * 100%.
    if (offset > 0) {
      const effectiveDuration = fileDuration > 0 ? fileDuration : (rawDisplayDuration + offset);
      const widthPercent = (effectiveDuration / rawDisplayDuration) * 100;
      const leftPercent = -(offset / rawDisplayDuration) * 100;

      return {
        isAligned: true,
        leftPercent,
        widthPercent,
        paddingLeftPercent: 0,
        alignmentLabel: "Waveform wyrównany do synchronizacji Clock",
      };
    }

    // Offset ujemny (teoretyczny przypadek wyprzedzenia):
    // punkt t=0 pliku pojawia się po upływie |offset| sekund contentu
    const paddingLeftPercent = (Math.abs(offset) / rawDisplayDuration) * 100;
    const effectiveDuration = fileDuration > 0 ? fileDuration : rawDisplayDuration;
    const widthPercent = (effectiveDuration / rawDisplayDuration) * 100;

    return {
      isAligned: true,
      leftPercent: 0,
      widthPercent,
      paddingLeftPercent,
      alignmentLabel: "Waveform wyrównany do synchronizacji Clock",
    };
  };

  const accTrack = computeTrack(rawAccOffset, accFileDuration, "Acceptance");
  const emiTrack = computeTrack(rawEmiOffset, emiFileDuration, "Emission");

  const hasActiveAlignment = accTrack.isAligned || emiTrack.isAligned;

  return {
    hasActiveAlignment,
    acceptance: accTrack,
    emission: emiTrack,
  };
}
