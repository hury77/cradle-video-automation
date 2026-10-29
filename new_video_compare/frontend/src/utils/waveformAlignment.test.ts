import {
  calculateWaveformTransforms,
  WaveformTimelineOffsets,
} from './waveformAlignment';

describe('calculateWaveformTransforms', () => {
  it('bez Clock/slate (offsety 0s): waveform pozostaje bez zmian (100% width, 0% left, isAligned=false)', () => {
    const offsets: WaveformTimelineOffsets = {
      acceptanceOffset: 0,
      emissionOffset: 0,
      displayDuration: 30,
    };
    const result = calculateWaveformTransforms(offsets, 30, 30);

    expect(result.hasActiveAlignment).toBe(false);
    expect(result.acceptance.isAligned).toBe(false);
    expect(result.acceptance.leftPercent).toBe(0);
    expect(result.acceptance.widthPercent).toBe(100);
    expect(result.acceptance.alignmentLabel).toBeNull();

    expect(result.emission.isAligned).toBe(false);
    expect(result.emission.leftPercent).toBe(0);
    expect(result.emission.widthPercent).toBe(100);
    expect(result.emission.alignmentLabel).toBeNull();
  });

  it('Emission z Clock (10s offset w 40s pliku, 30s contentu): waveform contentu jest wyrównany do Acceptance', () => {
    const offsets: WaveformTimelineOffsets = {
      acceptanceOffset: 0,
      emissionOffset: 10,
      displayDuration: 30,
    };
    const result = calculateWaveformTransforms(offsets, 30, 40);

    expect(result.hasActiveAlignment).toBe(true);

    // Acceptance: brak alignmentu
    expect(result.acceptance.isAligned).toBe(false);
    expect(result.acceptance.leftPercent).toBe(0);
    expect(result.acceptance.widthPercent).toBe(100);
    expect(result.acceptance.alignmentLabel).toBeNull();

    // Emission: wyrównany
    expect(result.emission.isAligned).toBe(true);
    // 40s / 30s = 133.333%
    expect(result.emission.widthPercent).toBeCloseTo(133.333, 2);
    // -10s / 30s = -33.333%
    expect(result.emission.leftPercent).toBeCloseTo(-33.333, 2);
    expect(result.emission.paddingLeftPercent).toBe(0);
    expect(result.emission.alignmentLabel).toBe('Waveform wyrównany do synchronizacji Clock');
  });

  it('Acceptance z Clock (10s offset w Acceptance): Acceptance zostaje przesunięty w lewo', () => {
    const offsets: WaveformTimelineOffsets = {
      acceptanceOffset: 10,
      emissionOffset: 0,
      displayDuration: 30,
    };
    const result = calculateWaveformTransforms(offsets, 40, 30);

    expect(result.hasActiveAlignment).toBe(true);
    expect(result.acceptance.isAligned).toBe(true);
    expect(result.acceptance.leftPercent).toBeCloseTo(-33.333, 2);
    expect(result.acceptance.widthPercent).toBeCloseTo(133.333, 2);
    expect(result.acceptance.alignmentLabel).toBe('Waveform wyrównany do synchronizacji Clock');

    expect(result.emission.isAligned).toBe(false);
    expect(result.emission.leftPercent).toBe(0);
  });

  it('obsługa ujemnego offsetu (teoretyczne opóźnienie pliku): renderuje właściwy paddingLeft', () => {
    const offsets: WaveformTimelineOffsets = {
      acceptanceOffset: 0,
      emissionOffset: -5,
      displayDuration: 25,
    };
    const result = calculateWaveformTransforms(offsets, 25, 20);

    expect(result.hasActiveAlignment).toBe(true);
    expect(result.emission.isAligned).toBe(true);
    // Padding 5s / 25s = 20%
    expect(result.emission.paddingLeftPercent).toBeCloseTo(20, 2);
    expect(result.emission.leftPercent).toBe(0);
    expect(result.emission.alignmentLabel).toBe('Waveform wyrównany do synchronizacji Clock');
  });

  it('brak / niepoprawne dane (fail-safe fallback do raw bez crasha)', () => {
    // null / undefined
    const resNull = calculateWaveformTransforms(null);
    expect(resNull.hasActiveAlignment).toBe(false);
    expect(resNull.acceptance.widthPercent).toBe(100);
    expect(resNull.emission.widthPercent).toBe(100);

    // displayDuration = 0
    const resZero = calculateWaveformTransforms({
      acceptanceOffset: 10,
      emissionOffset: 0,
      displayDuration: 0,
    });
    expect(resZero.hasActiveAlignment).toBe(false);
    expect(resZero.acceptance.leftPercent).toBe(0);
    expect(resZero.emission.leftPercent).toBe(0);

    // wartości NaN / invalid
    const resNan = calculateWaveformTransforms({
      acceptanceOffset: NaN,
      emissionOffset: undefined,
      displayDuration: NaN,
    });
    expect(resNan.hasActiveAlignment).toBe(false);
    expect(resNan.acceptance.leftPercent).toBe(0);
  });

  it('potwierdza, że wejściowe obiekty offsets nie są mutowane', () => {
    const offsets: WaveformTimelineOffsets = Object.freeze({
      acceptanceOffset: 0,
      emissionOffset: 10,
      displayDuration: 30,
    });

    // Powinno wykonać się bez błędu z zamrożonym obiektem
    const result = calculateWaveformTransforms(offsets, 30, 40);
    expect(result.hasActiveAlignment).toBe(true);
    expect(offsets.emissionOffset).toBe(10);
    expect(offsets.displayDuration).toBe(30);
  });

  it('symuluje uruchomienie redraw (setOptions) WaveSurfer po zmianie transformacji', () => {
    // Mock instancji WaveSurfer v7
    const mockWs = {
      setOptions: jest.fn(),
      getDuration: jest.fn().mockReturnValue(40),
    };

    const prevOffsets: WaveformTimelineOffsets = {
      acceptanceOffset: 0,
      emissionOffset: 0,
      displayDuration: 30,
    };
    const nextOffsets: WaveformTimelineOffsets = {
      acceptanceOffset: 0,
      emissionOffset: 10,
      displayDuration: 30,
    };

    const prevTransform = calculateWaveformTransforms(prevOffsets, 30, 40);
    const nextTransform = calculateWaveformTransforms(nextOffsets, 30, 40);

    expect(prevTransform.emission.leftPercent).toBe(0);
    expect(nextTransform.emission.leftPercent).toBeCloseTo(-33.333, 2);

    // Kiedy waveformTransforms ulega zmianie, komponent wywołuje setOptions({})
    if (prevTransform !== nextTransform && mockWs) {
      mockWs.setOptions({});
    }

    expect(mockWs.setOptions).toHaveBeenCalledTimes(1);
    expect(mockWs.setOptions).toHaveBeenCalledWith({});
  });
});

