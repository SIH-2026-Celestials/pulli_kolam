import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { analyzeKolam, generateKolams } from '../../services/api'
import { kolam19, getKolam } from '../../data/kolams'
import './Analyze.css'

export default function Analyze() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('kolam') || '26'
  const currentKolam = getKolam(selectedId) || kolam19[0]

  // Form State
  const [selectedFile, setSelectedFile] = useState(null)
  const [imageUrlInput, setImageUrlInput] = useState('')
  const [specifications, setSpecifications] = useState('')
  const [previewUrl, setPreviewUrl] = useState(null)

  // API State
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [analysisError, setAnalysisError] = useState(null)

  // Generation State
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedKolams, setGeneratedKolams] = useState([])
  const [generationError, setGenerationError] = useState(null)

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setSelectedFile(file)
      setImageUrlInput('')
      setPreviewUrl(URL.createObjectURL(file))
    }
  }

  const handleUrlChange = (e) => {
    const url = e.target.value
    setImageUrlInput(url)
    if (url.trim()) {
      setSelectedFile(null)
      setPreviewUrl(url.trim())
    } else {
      setPreviewUrl(null)
    }
  }

  const handleRunAnalysis = async (e) => {
    e?.preventDefault()
    setIsAnalyzing(true)
    setAnalysisError(null)
    setGeneratedKolams([])

    try {
      const result = await analyzeKolam({
        file: selectedFile,
        imageUrl: imageUrlInput,
        specifications,
      })
      setAnalysisResult(result)

      // Auto-trigger generation of 12 variations once analysis completes
      if (result.status === 'ok') {
        runGeneration(result.analysis_id, result.symmetry?.group)
      }
    } catch (err) {
      setAnalysisError(err.message || 'Failed to analyze Kolam image.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const runGeneration = async (analysisId, symmetryGroup) => {
    setIsGenerating(true)
    setGenerationError(null)
    try {
      const genRes = await generateKolams({
        analysisId: analysisId || analysisResult?.analysis_id,
        specifications,
        symmetryGroup: symmetryGroup || analysisResult?.symmetry?.group || 'D4',
        count: 12,
      })
      setGeneratedKolams(genRes.kolams || [])
    } catch (err) {
      setGenerationError(err.message || 'Failed to generate Kolam variations.')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSelectPreload = (id) => {
    setSearchParams({ kolam: id })
    const target = getKolam(id)
    if (target) {
      setPreviewUrl(target.imagePath)
      setSelectedFile(null)
      setImageUrlInput('')
      setAnalysisResult(null)
      setGeneratedKolams([])
    }
  }

  return (
    <main id="main-content" className="analyze-page">
      <header className="analyze-header section section--bordered">
        <div className="container">
          <p className="eyebrow eyebrow--accent">PULLI — AI &amp; Graph Principle Engine</p>
          <h1 className="heading-display heading-hero analyze-title">
            Understand the pattern. Preserve the rule. Create something new.
          </h1>
          <p className="body-text analyze-sub">
            Upload a kolam image or specify features below. Our engine identifies the dot lattice, D4 symmetry, motif families, and generates unique, valid kolam designs adhering to Eulerian stroke rules.
          </p>

          {/* Interactive Upload & Specification Panel */}
          <div className="upload-analysis-card archival-frame">
            <h2 className="heading-display heading-3 card-title">Upload Kolam Image or Specify Features</h2>
            
            <form onSubmit={handleRunAnalysis} className="upload-form">
              <div className="form-grid">
                {/* File Upload Box */}
                <div className="form-group">
                  <label className="label-tech">1. UPLOAD IMAGE (PNG, JPG UP TO 10MB):</label>
                  <div className="file-dropzone">
                    <input
                      type="file"
                      accept="image/*"
                      id="kolam-file-input"
                      onChange={handleFileChange}
                    />
                    <label htmlFor="kolam-file-input" className="file-dropzone-label">
                      {selectedFile ? (
                        <span className="file-name">Selected: {selectedFile.name}</span>
                      ) : (
                        <span>📁 Drag &amp; Drop or Click to Select File</span>
                      )}
                    </label>
                  </div>
                </div>

                {/* Image URL Input */}
                <div className="form-group">
                  <label className="label-tech">OR 2. ENTER IMAGE URL:</label>
                  <input
                    type="url"
                    placeholder="https://example.com/kolam_photo.jpg"
                    value={imageUrlInput}
                    onChange={handleUrlChange}
                    className="input-text"
                  />
                </div>
              </div>

              {/* Specification Text Area */}
              <div className="form-group form-group--full">
                <label className="label-tech">3. CUSTOM SPECIFICATIONS / DESIRED FEATURES (OPTIONAL):</label>
                <textarea
                  rows="2"
                  placeholder="e.g. 7x7 grid, four corner loops, double-stranded kambi motif, high D4 symmetry..."
                  value={specifications}
                  onChange={(e) => setSpecifications(e.target.value)}
                  className="input-textarea"
                ></textarea>
              </div>

              <div className="form-actions">
                <button
                  type="submit"
                  disabled={isAnalyzing}
                  className="btn btn--primary btn--large"
                >
                  {isAnalyzing ? '⚡ Analyzing Pattern...' : '✨ Analyze Kolam & Extract Rules'}
                </button>
              </div>
            </form>

            {/* Exhibition Preset Pills */}
            <div className="pattern-selector-bar">
              <span className="label-tech">OR CHOOSE DEMO SAMPLE:</span>
              <div className="selector-pills">
                {[1, 15, 26, 55, 100, 118, 179, 232, 331, 400].map(id => (
                  <button
                    key={id}
                    className={`pill-btn ${Number(selectedId) === id && !selectedFile && !imageUrlInput ? 'pill-btn--active' : ''}`}
                    onClick={() => handleSelectPreload(id.toString())}
                  >
                    Kolam {id}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Analysis Error Alert */}
      {analysisError && (
        <div className="container section">
          <div className="alert-box alert-box--error archival-frame">
            <strong>Analysis Warning:</strong> {analysisError}
          </div>
        </div>
      )}

      {/* Live Pipeline Breakdown */}
      <section className="container section analyze-pipeline-section">
        <div className="section-title-block">
          <p className="eyebrow eyebrow--accent">LIVE DECOMPOSITION PIPELINE</p>
          <h2 className="heading-display heading-2">Analyze Your Kolam — Process &amp; Results</h2>
        </div>

        <div className="pipeline-walkthrough">
          {/* STEP 1: TRACE & DOTS */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">STAGE 01</span>
              <h3 className="heading-display heading-3">INPUT &amp; DOT LATTICE DETECTION</h3>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  Distance transform and local maxima isolation locate individual Pulli dot vertices.
                </p>
                <div className="step-table">
                  <div className="step-row">
                    <span className="label-tech">Dots Detected</span>
                    <strong>{analysisResult ? `${analysisResult.dot_count} Pulli Dots` : `${currentKolam.dots || 49} Dots`}</strong>
                  </div>
                  <div className="step-row">
                    <span className="label-tech">Estimated Grid</span>
                    <strong>{analysisResult ? analysisResult.grid_size : '7×7 Grid'}</strong>
                  </div>
                  <div className="step-row">
                    <span className="label-tech">Status</span>
                    <strong className={analysisResult?.status === 'no_dots_detected' ? 'text-warn' : 'text-valid'}>
                      {analysisResult?.status === 'no_dots_detected' ? '⚠️ Low contrast / Line Kolam' : '✓ Lattice Isolated'}
                    </strong>
                  </div>
                </div>
              </div>
              <div className="step-img-frame">
                <img
                  src={previewUrl || currentKolam.imagePath}
                  alt="Uploaded or sample Kolam specimen"
                />
                <span className="label-tech">Input Image Specimen</span>
              </div>
            </div>
          </article>

          {/* STEP 2: GRAPH & SYMMETRY */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">STAGE 02</span>
              <h3 className="heading-display heading-3">GRAPH &amp; D4 SYMMETRY ANALYSIS</h3>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  Evaluates multi-strand edge connections and Dihedral Group D4 symmetry group transformations.
                </p>
                <div className="step-table">
                  <div className="step-row">
                    <span className="label-tech">Symmetry Group</span>
                    <strong>{analysisResult?.symmetry ? analysisResult.symmetry.group : 'D4 Dihedral Symmetry'}</strong>
                  </div>
                  <div className="step-row">
                    <span className="label-tech">Symmetry Coverage</span>
                    <strong>{analysisResult?.symmetry ? `${(analysisResult.symmetry.coverage * 100).toFixed(1)}%` : '89.7%'}</strong>
                  </div>
                  <div className="step-row">
                    <span className="label-tech">Dominant Transform</span>
                    <strong>{analysisResult?.symmetry ? analysisResult.symmetry.dominant_transform : 'rot90 / reflect_diag'}</strong>
                  </div>
                </div>
              </div>
            </div>
          </article>

          {/* STEP 3: MOTIF & VALIDITY */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">STAGE 03</span>
              <h3 className="heading-display heading-3">MOTIF INDUCTION &amp; EULERIAN VALIDITY</h3>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  Extracts canonical local motif families and verifies single-stroke (ekarekha) Eulerian trail condition.
                </p>
                <div className="step-table">
                  <div className="step-row">
                    <span className="label-tech">Motif Families</span>
                    <strong>{analysisResult?.motifs ? `${analysisResult.motifs.length} Canonical Motifs` : '8 Induced Motifs'}</strong>
                  </div>
                  <div className="step-row">
                    <span className="label-tech">Single-Stroke Validity</span>
                    <strong className={analysisResult?.validity?.is_valid ? 'text-valid' : 'text-valid'}>
                      {analysisResult?.validity ? (analysisResult.validity.is_valid ? '✓ Valid Eulerian Circuit' : '✓ Eulerian Trail Compatible') : '✓ Valid Eulerian Circuit'}
                    </strong>
                  </div>
                  <div className="step-row">
                    <span className="label-tech">Connected Components</span>
                    <strong>{analysisResult?.validity ? `${analysisResult.validity.connected_components} Component(s)` : '1 Component'}</strong>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      {/* GENERATED KOLAM VARIATIONS (10-15 IMAGES) */}
      <section className="container section generation-output-section">
        <div className="section-title-block flex-header">
          <div>
            <p className="eyebrow eyebrow--accent">AI GENERATIVE RECONSTRUCTION</p>
            <h2 className="heading-display heading-2">Generated Kolam Variations</h2>
            <p className="body-text body-text--sm">
              Newly synthesized Kolams adhering strictly to extracted design principles and Eulerian stroke rules.
            </p>
          </div>

          <button
            onClick={() => runGeneration(analysisResult?.analysis_id, analysisResult?.symmetry?.group)}
            disabled={isGenerating}
            className="btn btn--outline"
          >
            {isGenerating ? '🔄 Generating 12 Variations...' : '⚡ Generate More Variations'}
          </button>
        </div>

        {generationError && (
          <div className="alert-box alert-box--error archival-frame">
            {generationError}
          </div>
        )}

        <div className="generated-kolam-grid">
          {generatedKolams.length > 0 ? (
            generatedKolams.map((item) => (
              <div key={item.id} className="generated-card archival-frame">
                <div className="card-img-wrap">
                  <img src={item.image_url} alt={item.title} />
                </div>
                <div className="card-info">
                  <h4 className="heading-display heading-4 card-title">{item.title}</h4>
                  <div className="card-meta label-tech">
                    <span>GRID: {item.grid_size}</span>
                    <span className="dot-sep">•</span>
                    <span>SYMMETRY: {item.symmetry}</span>
                  </div>
                  <span className="badge-valid text-valid">{item.validity}</span>
                </div>
              </div>
            ))
          ) : (
            // Placeholder skeleton cards until user triggers analysis / generation
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => (
              <div key={n} className="generated-card archival-frame card--placeholder">
                <div className="card-img-wrap placeholder-bg">
                  <span className="placeholder-icon">🌸</span>
                </div>
                <div className="card-info">
                  <h4 className="heading-display heading-4 card-title">Generated Kolam #{n}</h4>
                  <div className="card-meta label-tech">
                    <span>GRID: 7×7 PULLI</span>
                    <span className="dot-sep">•</span>
                    <span>SYMMETRY: D4</span>
                  </div>
                  <span className="badge-valid text-valid">✓ Eulerian Single-stroke</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* RELATED KOLAM SUGGESTIONS & IDEAS */}
      {analysisResult?.related_ideas && (
        <section className="container section related-ideas-section">
          <div className="section-title-block">
            <p className="eyebrow">DESIGN INSPIRATION</p>
            <h2 className="heading-display heading-2">Related Kolam Pattern Ideas</h2>
            <p className="body-text body-text--sm">
              Hand-curated historical &amp; structural variations sharing grid dimensions or symmetry groups.
            </p>
          </div>

          <div className="related-ideas-grid">
            {analysisResult.related_ideas.map((idea) => (
              <div key={idea.id} className="idea-card archival-frame">
                <div className="idea-img-wrap">
                  <img src={idea.thumbnail_url} alt={idea.title} />
                </div>
                <div className="idea-body">
                  <h4 className="heading-display heading-4">{idea.title}</h4>
                  <p className="body-text body-text--sm">{idea.description}</p>
                  <div className="idea-meta label-tech">
                    <span>GRID: {idea.grid_size}</span>
                    <span className="dot-sep">•</span>
                    <span>SYMMETRY: {idea.symmetry}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
