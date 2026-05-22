/**
 * DiffWorker — Web Worker for pixel-level video frame comparison
 *
 * Sensitivity thresholds from sensitivity_settings.md:
 *  - "automation" level: intensity > 30/255 → RED (certain difference)
 *  - "review" level:     intensity > 15/255 → YELLOW (possible compression artifact / border case)
 *
 * This runs in a background thread so the UI never freezes.
 */

export interface DiffWorkerRequest {
  acceptanceData: ImageData;
  emissionData: ImageData;
  width: number;
  height: number;
}

export interface DiffWorkerResponse {
  overlayData: ImageData;
  certaintDiffRatio: number;   // fraction of pixels flagged RED (automation threshold)
  reviewDiffRatio: number;     // fraction of pixels flagged YELLOW (review threshold)
  hasDifferences: boolean;
}

// Thresholds (intensity per channel, 0–255)
const THRESHOLD_AUTOMATION = 30; // certain difference (red)
const THRESHOLD_REVIEW = 15;     // border / possible compression artifact (yellow)

self.onmessage = (event: MessageEvent<DiffWorkerRequest>) => {
  const { acceptanceData, emissionData, width, height } = event.data;

  const totalPixels = width * height;
  const overlay = new Uint8ClampedArray(width * height * 4); // RGBA

  let certaintCount = 0;
  let reviewCount = 0;

  for (let i = 0; i < totalPixels; i++) {
    const idx = i * 4;

    // Absolute per-channel differences
    const dr = Math.abs(acceptanceData.data[idx]     - emissionData.data[idx]);
    const dg = Math.abs(acceptanceData.data[idx + 1] - emissionData.data[idx + 1]);
    const db = Math.abs(acceptanceData.data[idx + 2] - emissionData.data[idx + 2]);

    // Max channel difference (captures colour shifts, not just luminance)
    const maxDiff = Math.max(dr, dg, db);

    if (maxDiff > THRESHOLD_AUTOMATION) {
      // RED — certain difference
      overlay[idx]     = 220;
      overlay[idx + 1] = 38;
      overlay[idx + 2] = 38;
      overlay[idx + 3] = 200; // 78% opacity
      certaintCount++;
    } else if (maxDiff > THRESHOLD_REVIEW) {
      // YELLOW — review / compression borderline
      overlay[idx]     = 234;
      overlay[idx + 1] = 179;
      overlay[idx + 2] = 8;
      overlay[idx + 3] = 160; // 63% opacity
      reviewCount++;
    } else {
      // Transparent — no meaningful difference
      overlay[idx + 3] = 0;
    }
  }

  const overlayImageData = new ImageData(overlay, width, height);

  const response: DiffWorkerResponse = {
    overlayData: overlayImageData,
    certaintDiffRatio: certaintCount / totalPixels,
    reviewDiffRatio: reviewCount / totalPixels,
    hasDifferences: certaintCount > 0 || reviewCount > 0,
  };

  // Transfer the buffer to avoid copying (performance)
  // Cast to `any` to satisfy the overloaded DedicatedWorkerGlobalScope.postMessage signature
  (self as any).postMessage(response, [overlayImageData.data.buffer]);
};
