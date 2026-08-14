const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function analyzeKolam({ file, imageUrl, specifications }) {
  const formData = new FormData()
  if (file) {
    formData.append('image', file)
  }
  if (imageUrl) {
    formData.append('image_url', imageUrl)
  }
  if (specifications) {
    formData.append('specifications', specifications)
  }

  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to analyze Kolam image' }))
    throw new Error(err.detail || 'Analysis request failed')
  }

  return await response.json()
}

export async function generateKolams({ specifications, analysisId, symmetryGroup, count = 12 }) {
  const response = await fetch(`${API_BASE_URL}/api/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      analysis_id: analysisId,
      specifications,
      symmetry_group: symmetryGroup,
      count,
    }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to generate Kolams' }))
    throw new Error(err.detail || 'Generation request failed')
  }

  return await response.json()
}

export async function getGallery() {
  const response = await fetch(`${API_BASE_URL}/api/gallery`)
  if (!response.ok) {
    throw new Error('Failed to fetch gallery')
  }
  return await response.json()
}
