import { describe, it, expect } from 'vitest'
import { validateImageFile, ACCEPTED_IMAGE_TYPES, MAX_IMAGE_BYTES } from '../validateImageFile'

function makeFile({ type = 'image/png', size = 1024 } = {}) {
  const file = new File([new Uint8Array(size)], 'kolam.png', { type })
  return file
}

describe('validateImageFile', () => {
  it('rejects when no file is given', () => {
    expect(validateImageFile(null).valid).toBe(false)
  })

  it.each(ACCEPTED_IMAGE_TYPES)('accepts %s within the size limit', (type) => {
    const result = validateImageFile(makeFile({ type, size: 1024 }))
    expect(result.valid).toBe(true)
  })

  it('rejects an unsupported mime type', () => {
    const result = validateImageFile(makeFile({ type: 'application/pdf' }))
    expect(result.valid).toBe(false)
    expect(result.message).toMatch(/unsupported file type/i)
  })

  it('rejects a file over the max size', () => {
    const result = validateImageFile(makeFile({ size: MAX_IMAGE_BYTES + 1 }))
    expect(result.valid).toBe(false)
    expect(result.message).toMatch(/too large/i)
  })

  it('accepts a file exactly at the max size', () => {
    const result = validateImageFile(makeFile({ size: MAX_IMAGE_BYTES }))
    expect(result.valid).toBe(true)
  })
})
