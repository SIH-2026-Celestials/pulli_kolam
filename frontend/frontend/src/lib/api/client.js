/**
 * M4.2 Phase J: single centralized fetch client for the PULLI backend.
 * No component should call fetch() directly for backend requests --
 * everything routes through here, per the task's explicit
 * "do not scatter fetch() calls" rule.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT_MS = 30000;

/** @param {string} kind @param {string} message @param {number} [status] @param {string} [code] @returns {import('./types').ApiError} */
function apiError(kind, message, status, code) {
  return { kind, message, status, code };
}

/**
 * @param {string} path
 * @param {RequestInit} options
 * @returns {Promise<{data: any, error: null} | {data: null, error: import('./types').ApiError}>}
 */
async function request(path, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);

    let body;
    try {
      body = await res.json();
    } catch {
      return { data: null, error: apiError('unknown', 'Backend returned a non-JSON response', res.status) };
    }

    if (!res.ok) {
      // The backend attaches a stable machine-readable `code` alongside
      // the human-readable `error` message (see api/main.py's
      // _api_error) -- prefer switching on status code (stable contract)
      // with `code` carried through for callers that want finer-grained
      // handling than the `kind` bucket below provides.
      const message = body.error || `Request failed (${res.status})`;
      const code = body.code;
      if (res.status === 503) {
        return { data: null, error: apiError('model_unavailable', message, res.status, code) };
      }
      if (res.status === 413) {
        return { data: null, error: apiError('upload_too_large', message, res.status, code) };
      }
      if (res.status === 415 || res.status === 400) {
        return { data: null, error: apiError('invalid_image', message, res.status, code) };
      }
      if (res.status === 422) {
        return { data: null, error: apiError('invalid_request', message, res.status, code) };
      }
      return { data: null, error: apiError('unknown', message, res.status, code) };
    }

    return { data: body, error: null };
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      return { data: null, error: apiError('timeout', `Request timed out after ${DEFAULT_TIMEOUT_MS}ms`) };
    }
    return { data: null, error: apiError('backend_unavailable', 'Could not reach the PULLI backend. Is the API server running?') };
  }
}

/** @returns {Promise<{data: any, error: null} | {data: null, error: import('./types').ApiError}>} */
export function getHealth() {
  return request('/api/v1/health');
}

/** @returns {Promise<{data: any, error: null} | {data: null, error: import('./types').ApiError}>} */
export function getModelInfo() {
  return request('/api/v1/model');
}

/**
 * @param {File} imageFile
 * @param {import('./types').DetectorName} detector
 * @returns {Promise<{data: import('./types').DetectResult, error: null} | {data: null, error: import('./types').ApiError}>}
 */
export function detect(imageFile, detector = 'classical') {
  const form = new FormData();
  form.append('image', imageFile);
  form.append('detector', detector);
  return request('/api/v1/detect', { method: 'POST', body: form });
}

/**
 * @param {File} imageFile
 * @param {import('./types').DetectorName} detector
 * @returns {Promise<{data: import('./types').AnalyzeResult, error: null} | {data: null, error: import('./types').ApiError}>}
 */
export function analyze(imageFile, detector = 'classical') {
  const form = new FormData();
  form.append('image', imageFile);
  form.append('detector', detector);
  return request('/api/v1/analyze', { method: 'POST', body: form });
}

/**
 * @param {File} imageFile
 * @param {import('./types').DetectorName} detector
 */
export function reconstruct(imageFile, detector = 'classical') {
  const form = new FormData();
  form.append('image', imageFile);
  form.append('detector', detector);
  return request('/api/v1/reconstruct', { method: 'POST', body: form });
}

/**
 * @param {File} imageFile
 * @returns {Promise<{data: import('./types').CompareResult, error: null} | {data: null, error: import('./types').ApiError}>}
 */
export function compareDetectors(imageFile) {
  const form = new FormData();
  form.append('image', imageFile);
  return request('/api/v1/compare-detectors', { method: 'POST', body: form });
}

// Generation runs a real multi-restart structural search per candidate
// (engine.learned_generation) -- observed latency is ~10-55s PER
// CANDIDATE, not a fast lookup, so this needs a much longer client
// timeout than the 30s default every other (near-instant) endpoint uses.
const GENERATE_TIMEOUT_MS = 240000;

/**
 * M5: learned-scorer-guided structural generation. `seed` omitted lets
 * the backend pick a random seed (returned in the response, reusable
 * for a reproducible re-generation); `count` bounds how many candidates
 * come back in one call (server-enforced cap, see api/main.py).
 * @param {{seed?: number, count?: number}} [options]
 */
export function generate(options = {}) {
  return request(
    '/api/v1/generate',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(options) },
    GENERATE_TIMEOUT_MS
  );
}
