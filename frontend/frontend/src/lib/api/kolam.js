/**
 * M4.2 Phase J: Kolam-domain helpers built on top of client.js's raw
 * API calls. Keeps compare-mode's dot-matching/categorization logic out
 * of the page component.
 */

import {
  detect, analyze, reconstruct, compareDetectors, generate, getHealth, getModelInfo,
  createGeneration, getGeneration, getGenerationMathematics, getGenerationGraph, listModels,
} from './client';

export {
  detect, analyze, reconstruct, compareDetectors, generate, getHealth, getModelInfo,
  createGeneration, getGeneration, getGenerationMathematics, getGenerationGraph, listModels,
};

const MATCH_TOLERANCE_PX = 6.0;

/**
 * Categorizes a compare-detectors result's dots into agreement/
 * classical-only/ml-only groups, in ORIGINAL image pixel coordinates,
 * for the difference overlay (green = agreement, blue = ML-only,
 * red = classical-only).
 * @param {import('./types').CompareResult} compareResult
 * @returns {{agree: {x:number,y:number}[], mlOnly: {x:number,y:number}[], classicalOnly: {x:number,y:number}[]}}
 */
export function categorizeCompareDots(compareResult) {
  const classicalDots = compareResult.classical.detections || [];
  const mlDots = compareResult.ml.detections || [];

  const mlMatched = new Set();
  const agree = [];
  const classicalOnly = [];

  for (const c of classicalDots) {
    let matchedIdx = -1;
    let bestDist = Infinity;
    mlDots.forEach((m, idx) => {
      if (mlMatched.has(idx)) return;
      const d = Math.hypot(c.x - m.x, c.y - m.y);
      if (d < MATCH_TOLERANCE_PX && d < bestDist) {
        bestDist = d;
        matchedIdx = idx;
      }
    });
    if (matchedIdx >= 0) {
      mlMatched.add(matchedIdx);
      agree.push(c);
    } else {
      classicalOnly.push(c);
    }
  }

  const mlOnly = mlDots.filter((_, idx) => !mlMatched.has(idx));

  return { agree, mlOnly, classicalOnly };
}
