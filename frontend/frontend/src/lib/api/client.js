/**
 * M4.2 Phase J: single centralized fetch client for the PULLI backend.
 * No component should call fetch() directly for backend requests --
 * everything routes through here, per the task's explicit
 * "do not scatter fetch() calls" rule.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEFAULT_TIMEOUT_MS = 30000;

/** @param {string} kind @param {string} message @param {number} [status] @returns {import('./types').ApiError} */
function apiError(kind, message, status) {
  return { kind, message, status };
}

/**
 * @param {string} path
 * @param {RequestInit} options
 * @returns {Promise<{data: any, error: null} | {data: null, error: import('./types').ApiError}>}
 */
async function request(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

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
      if (res.status === 401) {
        return { data: null, error: apiError('unauthorized', body.error || body.detail || 'Not authenticated', res.status) };
      }
      if (res.status === 409) {
        return { data: null, error: apiError('conflict', body.error || body.detail || 'Already exists', res.status) };
      }
      if (res.status === 422) {
        return { data: null, error: apiError('invalid_input', describeValidationError(body), res.status) };
      }
      if (res.status === 503) {
        return { data: null, error: apiError('model_unavailable', body.error || 'Model unavailable', res.status) };
      }
      if (res.status === 400) {
        return { data: null, error: apiError('invalid_image', body.error || body.detail || 'Invalid request', res.status) };
      }
      return { data: null, error: apiError('unknown', body.error || body.detail || `Request failed (${res.status})`, res.status) };
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
