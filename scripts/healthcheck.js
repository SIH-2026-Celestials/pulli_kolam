// Runs as one of the three `concurrently` processes started by `npm run
// dev` (named "ML" -- see package.json). Does not run any ML code
// itself: it only polls the ALREADY-STARTED API's own /health and
// /model endpoints and reports what the API says. The model runs
// in-process inside api/main.py via api/detectors.py, exactly as
// before -- this script never imports torch or the model itself.

const API_BASE = process.env.PULLI_API_BASE_URL || 'http://localhost:8000';
const POLL_INTERVAL_MS = 500;
const TIMEOUT_MS = 60000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHealth() {
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/health`);
      if (res.ok) return res.json();
    } catch {
      // API not up yet -- keep polling.
    }
    await sleep(POLL_INTERVAL_MS);
  }
  return null;
}

async function main() {
  console.log(`Waiting for FastAPI backend at ${API_BASE} ...`);
  const health = await waitForHealth();

  if (!health) {
    console.error(`Backend did not become healthy within ${TIMEOUT_MS / 1000}s -- is uvicorn running?`);
    process.exitCode = 1;
    return;
  }

  console.log(`FastAPI running on ${API_BASE}`);
  console.log(`Health: ${JSON.stringify(health)}`);

  if (health.ml_detector_available !== true) {
    // Honest, not fatal: the API itself never silently substitutes
    // classical for ml (see api/detectors.py) -- this script just
    // surfaces the same fact at startup instead of waiting for a user's
    // first ML request to discover it.
    console.warn('ML detector available through API: false -- ML requests will return 503, not a silent classical fallback.');
  } else {
    console.log('ML detector available through API: true');
  }

  try {
    const modelRes = await fetch(`${API_BASE}/api/v1/model`);
    const model = await modelRes.json();
    console.log(`Model info: ${JSON.stringify(model)}`);
  } catch (err) {
    console.warn(`Could not fetch /api/v1/model: ${err.message}`);
  }
}

main();
