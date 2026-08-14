/**
 * Single source of truth for the Kolam ML pipeline stages.
 *
 * Stage IDs match the values emitted by the backend SSE events
 * (api/main.py :: _run_pipeline_in_thread).  Do NOT change IDs here
 * without updating the backend emit calls.
 *
 * Importing components must use KOLAM_STAGES for rendering -- they
 * must NOT define their own stage arrays.
 */

/** @type {ReadonlyArray<{id: string, label: string, shortMessage: string}>} */
export const KOLAM_STAGES = Object.freeze([
  {
    id: 'upload_image',
    label: 'Upload Image',
    shortMessage: 'Uploading image to the server…',
  },
  {
    id: 'detect_dots',
    label: 'Detect Dots',
    shortMessage: 'Running dot detection…',
  },
  {
    id: 'trace_stroke',
    label: 'Trace Stroke',
    shortMessage: 'Tracing stroke from dot grid…',
  },
  {
    id: 'build_graph',
    label: 'Build Graph',
    shortMessage: 'Converting stroke into a mathematical graph…',
  },
  {
    id: 'detect_symmetry',
    label: 'Detect Symmetry',
    shortMessage: 'Analysing structural symmetry…',
  },
  {
    id: 'find_motifs',
    label: 'Find Motifs',
    shortMessage: 'Identifying recurring motif patterns…',
  },
  {
    id: 'validate_stroke',
    label: 'Validate Stroke',
    shortMessage: 'Checking Eulerian stroke validity…',
  },
  {
    id: 'extract_rules',
    label: 'Extract Rules',
    shortMessage: 'Extracting Kolam design rules…',
  },
]);

/** Build the initial stage state array — all pending. */
export function makeInitialStages() {
  return KOLAM_STAGES.map((s) => ({
    id: s.id,
    label: s.label,
    status: 'pending',   // 'pending' | 'running' | 'completed' | 'failed'
    message: null,
    result: null,
    startedAt: null,
    completedAt: null,
  }));
}
