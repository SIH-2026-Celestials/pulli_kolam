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
    // 'include' on every request (not just auth ones) so the session
    // cookie -- HttpOnly, never touched from JS -- rides along
    // automatically once set; harmless for the image endpoints, which
    // ignore it entirely.
    const res = await fetch(`${API_BASE}${path}`, { ...options, credentials: 'include', signal: controller.signal });
    clearTimeout(timeoutId);

    // 204 No Content (logout) has no body to parse.
    if (res.status === 204) {
      return { data: null, error: null };
    }

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
      const message = body.error || body.detail || `Request failed (${res.status})`;
      const code = body.code;
      if (res.status === 401) {
        return { data: null, error: apiError('unauthorized', message, res.status, code) };
      }
      if (res.status === 409) {
        return { data: null, error: apiError('conflict', message, res.status, code) };
      }
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
        return { data: null, error: apiError('invalid_input', describeValidationError(body) || message, res.status, code) };
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

/** FastAPI/pydantic validation errors (422) come back as {detail: [{msg, loc}, ...]} -- flatten to one readable string. */
function describeValidationError(body) {
  if (Array.isArray(body?.detail) && body.detail.length) {
    return body.detail.map((d) => d.msg).join(' ');
  }
  return body?.detail || body?.error || 'Invalid input.';
}

function postJson(path, payload) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
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

// --- Auth (api/auth/router.py) ---
// Session state lives in an HttpOnly cookie set by the backend -- these
// calls never read or write a token themselves, only trigger the
// browser's normal cookie handling via credentials: 'include' (above).

/**
 * @param {{email: string, password: string, displayName: string}} params
 * @returns {Promise<{data: import('./types').User, error: null} | {data: null, error: import('./types').ApiError}>}
 */
export function register({ email, password, displayName }) {
  return postJson('/api/v1/auth/register', { email, password, display_name: displayName });
}

/**
 * @param {{email: string, password: string}} params
 * @returns {Promise<{data: import('./types').User, error: null} | {data: null, error: import('./types').ApiError}>}
 */
export function login({ email, password }) {
  return postJson('/api/v1/auth/login', { email, password });
}

/** @returns {Promise<{data: null, error: null} | {data: null, error: import('./types').ApiError}>} */
export function logout() {
  return request('/api/v1/auth/logout', { method: 'POST' });
}

/** @returns {Promise<{data: import('./types').User, error: null} | {data: null, error: import('./types').ApiError}>} */
export function getMe() {
  return request('/api/v1/auth/me');
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

/**
 * M7 platform: PERSISTED generation -- same underlying M5 search as
 * generate() above (same latency profile, same timeout), but each
 * candidate is written to the database and individually retrievable
 * afterward via getGeneration(id) (generation history). Response
 * candidates include `id` (for later lookup) and `analysis` (the full
 * Mathematics panel data), so the initial call already has everything
 * needed for the main studio view -- getGeneration/getGenerationGraph
 * are for on-demand detail (history browsing, graph view), not
 * required for the primary render.
 * @param {{seed?: number, count?: number, verify_recognizer?: boolean}} [options]
 */
export function createGeneration(options = {}) {
  return request(
    '/api/v1/generations',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(options) },
    GENERATE_TIMEOUT_MS
  );
}

/** @param {string} id GenerationResult id */
export function getGeneration(id) {
  return request(`/api/v1/generations/${id}`);
}

/** @param {string} id GenerationResult id */
export function getGenerationMathematics(id) {
  return request(`/api/v1/generations/${id}/mathematics`);
}

/** @param {string} id GenerationResult id */
export function getGenerationGraph(id) {
  return request(`/api/v1/generations/${id}/graph`);
}

/**
 * M7 platform: paginated generation history -- a LIGHT payload per row
 * (no SVG/representation, see api/routes_generations.py's list_generations),
 * for a history browser to page through without fetching full detail
 * for every row.
 * @param {number} [page]
 * @param {number} [pageSize]
 */
export function listGenerations(page = 1, pageSize = 20) {
  return request(`/api/v1/generations?page=${page}&page_size=${pageSize}`);
}

/**
 * M7 platform: build a direct download URL for a generation result's
 * artifact (SVG/PNG/JSON). Not fetched through `request()` -- this is
 * meant for a plain `<a href>`/`window.open`, so the browser handles
 * the download natively via the backend's Content-Disposition header.
 * @param {string} id GenerationResult id
 * @param {'svg'|'png'|'json'} format
 */
export function generationExportUrl(id, format = 'svg') {
  return `${API_BASE}/api/v1/generations/${id}/export?format=${format}`;
}

/** @returns {Promise<{data: any, error: null} | {data: null, error: import('./types').ApiError}>} */
export function listModels() {
  return request('/api/v1/models');
}
