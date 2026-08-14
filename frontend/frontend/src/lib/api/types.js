/**
 * M4.2 Phase J: shared JSDoc type definitions for the PULLI API client.
 *
 * This project has no TypeScript (verified before adding anything --
 * see docs/M4_2_IMPLEMENTATION_PLAN.md's "Scope decisions"). These
 * JSDoc typedefs give editor autocomplete/type-checking (via VS Code's
 * built-in JS language service) without introducing a TS build step --
 * the closest honest equivalent to "typed" for a plain-JS project.
 *
 * @typedef {'classical'|'ml'} DetectorName
 *
 * @typedef {Object} Detection
 * @property {number} x
 * @property {number} y
 *
 * @typedef {Object} DetectResult
 * @property {boolean} success
 * @property {DetectorName} detector
 * @property {string|null} model_version
 * @property {{width: number, height: number}} image
 * @property {Detection[]} detections
 * @property {number} count
 * @property {number} processing_ms
 *
 * @typedef {Object} GraphSummary
 * @property {number} nodes
 * @property {number} edges
 * @property {number} distinct_edges
 *
 * @typedef {Object} AnalyzeResult
 * @property {boolean} success
 * @property {DetectorName} detector
 * @property {string|null} model_version
 * @property {Detection[]} dots
 * @property {number} dot_count
 * @property {number} processing_ms
 * @property {GraphSummary} graph
 * @property {{motif_count: number}} motifs
 * @property {{is_eulerian_circuit: boolean, has_eulerian_path: boolean, connected_components: number, largest_component_covers_all_nodes: boolean}} validity
 *
 * @typedef {Object} CompareSide
 * @property {DetectorName} detector
 * @property {string|null} model_version
 * @property {Detection[]} detections
 * @property {number} count
 * @property {number} processing_ms
 * @property {string|null} error
 *
 * @typedef {Object} CompareResult
 * @property {boolean} success
 * @property {{width: number, height: number}} image
 * @property {CompareSide} classical
 * @property {CompareSide} ml
 * @property {{agreeing_dots: number, classical_only: number, ml_only: number}} agreement
 *
 * @typedef {Object} ApiError
 * @property {'network'|'timeout'|'invalid_image'|'model_unavailable'|'backend_unavailable'|'unauthorized'|'conflict'|'invalid_input'|'unknown'} kind
 * @property {string} message
 * @property {number} [status]
 *
 * @typedef {Object} User
 * @property {number} id
 * @property {string} email
 * @property {string} display_name
 * @property {string} created_at
 * @property {string|null} last_login_at
 */

export {};
