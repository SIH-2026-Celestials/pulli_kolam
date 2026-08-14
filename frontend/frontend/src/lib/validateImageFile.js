/**
 * Shared client-side validation for images headed to the /detect page,
 * used both by the Home hero's upload CTA and the Detect page's own
 * dropzone. The backend (api/main.py) enforces the real rules -- this
 * only gives the user immediate feedback instead of waiting on a round
 * trip for something checkable locally.
 */

export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp']
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024 // 10MB, matches Hero's prior check

/**
 * @param {File} file
 * @returns {{ valid: true } | { valid: false, message: string }}
 */
export function validateImageFile(file) {
  if (!file) return { valid: false, message: 'No file selected.' }
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    return { valid: false, message: 'Unsupported file type. Please upload a JPEG, PNG, WebP, or BMP image.' }
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return { valid: false, message: 'File is too large. Maximum size is 10MB.' }
  }
  return { valid: true }
}
