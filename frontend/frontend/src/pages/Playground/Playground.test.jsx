/* global process */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import Playground from './Playground'
import { LanguageProvider } from '../../context/LanguageContext'
import { AuthProvider } from '../../context/AuthContext'

const REAL_CANDIDATE = {
  id: 'result-real-1',
  seed: 4242,
  is_valid: true,
  render_svg: '<svg data-testid="real-svg"><circle cx="1" cy="1" r="1" /></svg>',
  graph: { dot_points: [[0, 0], [1, 0]], edges: [[[0, 0], [1, 0]]], degree_distribution: {} },
  analysis: {
    graph: { vertices: 42, edges: 80, distinct_edges: 60, connected_components: 1 },
    eulerian: { odd_degree_vertex_count: 0, is_eulerian_circuit: true, has_eulerian_path: true },
    multiplicity: { max_multiplicity: 2, violations: 0 },
    symmetry: { coverage: 0.77 },
    complexity: { complexity_score: 0.5, density_score: 0.3 },
    novelty: { novelty_score: 0.91, nearest_source_id: null },
  },
  verification: {
    structural_hard_gate: { method: 'structural_hard_gate', is_valid: true, notes: 'connected_components=1, odd_degree_nodes=0' },
  },
  novelty: { novelty_score: 0.91, nearest_source_id: null, is_exact_duplicate: false },
  generation_time_ms: 5432,
  latency_ms: 5432,
}

const mockCreateGeneration = vi.fn()
const mockGetHealth = vi.fn()
const mockGetModelInfo = vi.fn()
const mockListGenerations = vi.fn()
const mockGetGeneration = vi.fn()

vi.mock('../../lib/api/kolam', () => ({
  createGeneration: (...args) => mockCreateGeneration(...args),
  getHealth: (...args) => mockGetHealth(...args),
  getModelInfo: (...args) => mockGetModelInfo(...args),
  listGenerations: (...args) => mockListGenerations(...args),
  getGeneration: (...args) => mockGetGeneration(...args),
  generationExportUrl: (id, format = 'svg') => `http://localhost:8000/api/v1/generations/${id}/export?format=${format}`,
  // AuthContext calls these on mount/action -- not under test here, but
  // must exist on the mock or AuthProvider's refresh() throws.
  getMe: () => Promise.resolve({ data: null, error: { message: 'not authenticated' } }),
  login: () => Promise.resolve({ data: null, error: null }),
  logout: () => Promise.resolve({ data: null, error: null }),
  register: () => Promise.resolve({ data: null, error: null }),
}))

function renderPlayground() {
  const result = render(
    <MemoryRouter>
      <LanguageProvider>
        <AuthProvider>
          <Playground />
        </AuthProvider>
      </LanguageProvider>
    </MemoryRouter>
  )
  return within(result.container)
}

beforeEach(() => {
  mockCreateGeneration.mockReset()
  mockGetHealth.mockReset().mockResolvedValue({
    data: { status: 'ok', generation_service_available: true, gated_detector_available: true, database_connected: true },
    error: null,
  })
  mockGetModelInfo.mockReset().mockResolvedValue({ data: {}, error: null })
  mockListGenerations.mockReset().mockResolvedValue({ data: { items: [], total: 0 }, error: null })
  mockGetGeneration.mockReset()
})

afterEach(() => {
  cleanup()
})

describe('Playground — real generation flow', () => {
  it('renders the real backend SVG and real analysis after a successful generation', async () => {
    mockCreateGeneration.mockResolvedValue({
      data: { run_id: 'run-1', request_id: 'req-1', model_version: 'v1.0', total_latency_ms: 5432, candidates: [REAL_CANDIDATE] },
      error: null,
    })
    const view = renderPlayground()

    fireEvent.click(view.getByRole('button', { name: /generate kolam/i }))

    await waitFor(() => expect(view.getByText(/^Generated$/)).toBeInTheDocument())

    // The real SVG the backend returned is what's on screen.
    expect(view.getByTestId('real-svg')).not.toBeNull()
    // Real analysis numbers, not placeholders.
    expect(view.getByText('42')).toBeInTheDocument() // vertices
    expect(view.getByText('77%')).toBeInTheDocument() // symmetry coverage
  })

  it('shows a real, honest error state on backend failure — never fabricated data', async () => {
    mockCreateGeneration.mockResolvedValue({
      data: null,
      error: { message: 'Could not reach the PULLI backend. Is the API server running?', code: 'backend_unavailable' },
    })
    const view = renderPlayground()

    fireEvent.click(view.getByRole('button', { name: /generate kolam/i }))

    await waitFor(() => expect(view.getByText(/Generation failed/i)).toBeInTheDocument())
    expect(view.getByText(/Could not reach the PULLI backend/i)).toBeInTheDocument()
    // No canvas/SVG should have been rendered as if generation succeeded.
    expect(view.queryByTestId('real-svg')).toBeNull()
  })

  it('rejects a non-integer seed before calling the backend at all', async () => {
    const view = renderPlayground()
    const seedInput = view.getByPlaceholderText('random')
    // type="number" inputs sanitize genuinely non-numeric text to '' in
    // jsdom (matching real browser behavior), so a fractional value is
    // used here to exercise the Number.isInteger rejection path instead.
    fireEvent.change(seedInput, { target: { value: '3.5' } })
    fireEvent.click(view.getByRole('button', { name: /generate kolam/i }))

    await waitFor(() => expect(view.getByText(/Seed must be a whole number/i)).toBeInTheDocument())
    expect(mockCreateGeneration).not.toHaveBeenCalled()
  })

  it('disables the Generate button while a request is in flight (no duplicate submits)', async () => {
    let resolveFn
    mockCreateGeneration.mockReturnValue(new Promise((resolve) => { resolveFn = resolve }))
    const view = renderPlayground()

    const btn = view.getByRole('button', { name: /generate kolam/i })
    fireEvent.click(btn)
    await waitFor(() => expect(btn).toBeDisabled())

    resolveFn({ data: { run_id: 'r', request_id: 'q', model_version: 'v1.0', total_latency_ms: 100, candidates: [REAL_CANDIDATE] }, error: null })
    await waitFor(() => expect(btn).not.toBeDisabled())
  })

  it('reflects real backend health checks, never a hardcoded "Connected"', async () => {
    mockGetHealth.mockResolvedValue({ data: null, error: { message: 'down' } })
    const view = renderPlayground()
    await waitFor(() => expect(view.getAllByText('OFFLINE').length).toBeGreaterThan(0))
  })
})

describe('No fabricated data in the frontend source', () => {
  // process.cwd() is frontend/frontend/ when vitest runs (matches this
  // project's package.json location) -- avoids relying on import.meta.url
  // being a real file:// URL, which vitest's transform pipeline doesn't
  // guarantee for every module.
  const srcRoot = join(process.cwd(), 'src') + '/'
  const filesToScan = [
    'pages/Playground/Playground.jsx',
    'components/GeneratedVariations/GeneratedVariations.jsx',
    'components/RecentKolams/RecentKolams.jsx',
    'context/AuthContext.jsx',
  ]
  const bannedPatterns = [
    /FALLBACK_CANDIDATES/,
    /MOCK_KOLAM_ITEMS/,
    /sample_gen_/,
    /mock_\d/,
    /static\/synthetic\/kolam19_1\.jpg/,
  ]

  it.each(filesToScan)('%s contains no fabricated fallback data', (relPath) => {
    const contents = readFileSync(srcRoot + relPath, 'utf-8')
    for (const pattern of bannedPatterns) {
      expect(contents).not.toMatch(pattern)
    }
  })
})
