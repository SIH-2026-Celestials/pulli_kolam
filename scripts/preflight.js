// Runs automatically via npm's "predev" lifecycle hook, before `npm run
// dev` starts anything. Fails fast and clearly rather than letting the
// API or frontend start into a broken state -- see package.json.
//
// Does NOT touch API contracts, ML inference logic, detector behavior,
// or engine code -- this only checks that required files/deps exist
// before spawning the existing, unmodified startup commands.

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');

function fail(message) {
  console.error(`\n${message}\n`);
  process.exit(1);
}

// 1. ML checkpoint must exist. api/detectors.py's MLDetector loads this
// lazily on first ML request and raises explicitly (never silently
// falls back to classical) if it's missing -- but failing here, before
// the API even starts, gives a much clearer signal for local dev than
// waiting for the first ML request to 503.
const CHECKPOINT_REL = path.join('experiments', 'm4_2', 'results', 'dot_heatmap_net_v2.pt');
const checkpointPath = path.join(ROOT, CHECKPOINT_REL);
if (!fs.existsSync(checkpointPath)) {
  fail(`ML checkpoint missing:\n${CHECKPOINT_REL.replace(/\\/g, '/')}`);
}
console.log(`[PREFLIGHT] ML checkpoint found: ${CHECKPOINT_REL.replace(/\\/g, '/')}`);

// 2. Frontend dependencies must exist before Vite can start. Install
// them automatically if missing, rather than letting `npm run dev`
// fail deep inside the frontend process with a confusing error.
const frontendDir = path.join(ROOT, 'frontend', 'frontend');
const frontendNodeModules = path.join(frontendDir, 'node_modules');
if (!fs.existsSync(frontendNodeModules)) {
  console.log('[PREFLIGHT] frontend/frontend/node_modules missing -- running npm install there first...');
  const result = spawnSync('npm', ['install'], { cwd: frontendDir, stdio: 'inherit', shell: true });
  if (result.status !== 0) {
    fail('[PREFLIGHT] npm install failed in frontend/frontend -- see output above.');
  }
} else {
  console.log('[PREFLIGHT] frontend/frontend/node_modules present.');
}

// 3. Python must be reachable, since the API command below is a plain
// `python -m uvicorn ...` (unmodified, per the task's exact command).
// process.platform check (not `shell: true`) avoids Node's child_process
// deprecation warning about unescaped shell arguments -- `python` on
// Windows resolves via PATHEXT without needing a shell.
const pythonCheck = spawnSync(process.platform === 'win32' ? 'python.exe' : 'python', ['--version']);
if (pythonCheck.status !== 0) {
  fail('[PREFLIGHT] `python` was not found on PATH -- required to run the FastAPI backend.');
}

console.log('[PREFLIGHT] All checks passed.\n');
