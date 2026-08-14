/**
 * useKolamAnalysis — React hook that manages the full lifecycle of a
 * streaming Kolam analysis job.
 *
 * Responsibilities:
 *  - POST image to /api/v1/analyze-stream/start → receive job_id
 *  - Open SSE connection to /api/v1/analyze-stream/{job_id}/events
 *  - Parse stage_started / stage_completed / stage_failed / pipeline_* events
 *  - Update stage state — NO fake timers, backend events are the only
 *    thing that advances stage status
 *  - Collect intermediate per-stage results
 *  - Close SSE connection on completion, failure, or unmount
 *  - Prevent duplicate connections
 *
 * Usage:
 *   const { analysisState, startAnalysis, reset } = useKolamAnalysis()
 *
 * analysisState shape:
 *   {
 *     status:       'idle' | 'uploading' | 'running' | 'completed' | 'failed'
 *     jobId:        string | null
 *     detector:     'classical' | 'ml'
 *     currentStage: number            -- index of the currently active stage (-1 = none)
 *     stages:       AnalysisStage[]   -- see analysisStages.js
 *     error:        string | null
 *     results:      Record<stageId, result>
 *     activeMessage: string | null    -- live message from the active stage
 *   }
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { makeInitialStages } from '../analysisStages';
import { validateImageFile } from '../validateImageFile';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function makeInitialState() {
  return {
    status: 'idle',
    jobId: null,
    detector: 'classical',
    currentStage: -1,
    stages: makeInitialStages(),
    error: null,
    results: {},
    activeMessage: null,
  };
}

export function useKolamAnalysis() {
  const [analysisState, setAnalysisState] = useState(makeInitialState);
  const eventSourceRef = useRef(null);
  const isConnectedRef = useRef(false);

  /** Close any existing SSE connection cleanly. */
  const _closeSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    isConnectedRef.current = false;
  }, []);

  /** Close SSE on unmount. */
  useEffect(() => {
    return () => { _closeSSE(); };
  }, [_closeSSE]);

  /** Open SSE connection for a given job_id and wire event handlers. */
  const _connectSSE = useCallback((jobId) => {
    if (isConnectedRef.current) return; // prevent duplicate connections
    _closeSSE();

    const url = `${API_BASE}/api/v1/analyze-stream/${jobId}/events`;
    const es = new EventSource(url);
    eventSourceRef.current = es;
    isConnectedRef.current = true;

    /** Update a single stage by id within the stages array. */
    const patchStage = (stageId, patch) => {
      setAnalysisState((prev) => ({
        ...prev,
        stages: prev.stages.map((s) => s.id === stageId ? { ...s, ...patch } : s),
      }));
    };

    /** Find stage index by id. */
    const stageIdx = (stageId) =>
      makeInitialStages().findIndex((s) => s.id === stageId);

    // ── stage_started ─────────────────────────────────────────────────
    es.addEventListener('stage_started', (e) => {
      let data;
      try { data = JSON.parse(e.data); } catch { return; }
      patchStage(data.stage, {
        status: 'running',
        message: data.message || null,
        startedAt: new Date().toISOString(),
      });
      setAnalysisState((prev) => ({
        ...prev,
        status: 'running',
        currentStage: stageIdx(data.stage),
        activeMessage: data.message || null,
      }));
    });

    // ── stage_completed ───────────────────────────────────────────────
    es.addEventListener('stage_completed', (e) => {
      let data;
      try { data = JSON.parse(e.data); } catch { return; }
      patchStage(data.stage, {
        status: 'completed',
        message: data.message || null,
        result: data.result || null,
        completedAt: new Date().toISOString(),
      });
      setAnalysisState((prev) => ({
        ...prev,
        results: { ...prev.results, [data.stage]: data.result || null },
      }));
    });

    // ── stage_failed ──────────────────────────────────────────────────
    es.addEventListener('stage_failed', (e) => {
      let data;
      try { data = JSON.parse(e.data); } catch { return; }
      patchStage(data.stage, {
        status: 'failed',
        message: data.message || 'Stage failed.',
        completedAt: new Date().toISOString(),
      });
    });

    // ── pipeline_completed ────────────────────────────────────────────
    es.addEventListener('pipeline_completed', (e) => {
      let data;
      try { data = JSON.parse(e.data); } catch { return; }
      setAnalysisState((prev) => ({
        ...prev,
        status: 'completed',
        currentStage: -1,
        activeMessage: data.message || 'Analysis complete.',
      }));
      _closeSSE();
    });

    // ── pipeline_failed ───────────────────────────────────────────────
    es.addEventListener('pipeline_failed', (e) => {
      let data;
      try { data = JSON.parse(e.data); } catch { return; }
      setAnalysisState((prev) => ({
        ...prev,
        status: 'failed',
        error: data.message || 'Analysis pipeline failed.',
        activeMessage: null,
      }));
      _closeSSE();
    });

    // ── SSE transport error ───────────────────────────────────────────
    es.onerror = () => {
      // Only surface as an error if the pipeline is still running.
      // A normal SSE close after pipeline_completed also fires onerror.
      setAnalysisState((prev) => {
        if (prev.status === 'completed' || prev.status === 'failed') return prev;
        return {
          ...prev,
          status: 'failed',
          error: 'Lost connection to the analysis server. The pipeline may still be running — try refreshing.',
          activeMessage: null,
        };
      });
      _closeSSE();
    };
  }, [_closeSSE]);

  /**
   * Start a new analysis job.
   * @param {File} imageFile
   * @param {'classical'|'ml'} detector
   */
  const startAnalysis = useCallback(async (imageFile, detector = 'classical') => {
    // Client-side validation before any network call -- same rules as /detect page.
    const validation = validateImageFile(imageFile)
    if (!validation.valid) {
      setAnalysisState(() => ({
        ...makeInitialState(),
        status: 'failed',
        error: validation.message,
      }))
      return
    }

    // Prevent starting while another job is already running.
    setAnalysisState((prev) => {
      if (prev.status === 'uploading' || prev.status === 'running') return prev;
      return {
        ...makeInitialState(),
        status: 'uploading',
        detector,
        activeMessage: 'Uploading image…',
      };
    });

    _closeSSE();

    // Upload the image and receive a job_id.
    const form = new FormData();
    form.append('image', imageFile);
    form.append('detector', detector);

    let jobId;
    try {
      const res = await fetch(`${API_BASE}/api/v1/analyze-stream/start`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Upload failed (${res.status})`);
      }
      const body = await res.json();
      jobId = body.job_id;
    } catch (err) {
      setAnalysisState((prev) => ({
        ...prev,
        status: 'failed',
        error: err.message || 'Failed to reach the analysis server.',
        activeMessage: null,
      }));
      return;
    }

    setAnalysisState((prev) => ({
      ...prev,
      jobId,
      status: 'running',
      activeMessage: 'Connecting to analysis stream…',
    }));

    _connectSSE(jobId);
  }, [_closeSSE, _connectSSE]);

  /** Reset state to idle (clears result + closes any open connection). */
  const reset = useCallback(() => {
    _closeSSE();
    setAnalysisState(makeInitialState());
  }, [_closeSSE]);

  return { analysisState, startAnalysis, reset };
}
