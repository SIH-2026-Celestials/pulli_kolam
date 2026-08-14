import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister } from '../lib/api/kolam'

const AuthContext = createContext(null)

const LOCAL_STORAGE_RECENT_KEY = 'pulli_recent_kolams'

// 'loading' | 'authenticated' | 'unauthenticated' | 'error'
// 'error' is distinct from 'unauthenticated' -- a 401 from /me genuinely
// means "no session," but a network failure means "we don't know," and
// those should not be presented to the user identically.
export function AuthProvider({ children }) {
  const [status, setStatus] = useState('loading')
  const [user, setUser] = useState(null)
  const [recentKolams, setRecentKolams] = useState(() => {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_RECENT_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  const refresh = useCallback(async () => {
    setStatus('loading')
    const { data, error } = await getMe()
    if (data) {
      setUser(data)
      setStatus('authenticated')
    } else if (error?.kind === 'unauthorized') {
      setUser(null)
      setStatus('unauthenticated')
    } else {
      // backend_unavailable / timeout / unknown -- a real failure to
      // determine auth state, not the same thing as "logged out."
      setUser(null)
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    const id = setTimeout(() => refresh(), 0)
    return () => clearTimeout(id)
  }, [refresh])

  const login = useCallback(async (email, password) => {
    const { data, error } = await apiLogin({ email, password })
    if (data) {
      setUser(data)
      setStatus('authenticated')
    }
    return { data, error }
  }, [])

  const register = useCallback(async (email, password, displayName) => {
    const { data, error } = await apiRegister({ email, password, displayName })
    if (data) {
      setUser(data)
      setStatus('authenticated')
    }
    return { data, error }
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
    setStatus('unauthenticated')
  }, [])

  // Local, device-scoped history of generated/analyzed Kolams. There is
  // no backend table for this (unlike users/sessions in api/auth/) --
  // it deliberately stays client-side only, same scope as the theme/
  // language preferences already kept in localStorage elsewhere.
  const addRecentKolam = useCallback((kolamItem) => {
    const newItem = {
      id: kolamItem.id || `kolam_${Date.now()}`,
      title: kolamItem.title || 'Generated Pulli Kolam',
      image_url: kolamItem.image_url || kolamItem.imagePath || '/static/synthetic/kolam19_1.jpg',
      grid_size: kolamItem.grid_size || '7×7',
      symmetry: kolamItem.symmetry || 'D4 Dihedral',
      validity: kolamItem.validity || '✓ Eulerian Single-stroke',
      created_at: new Date().toISOString(),
    }
    setRecentKolams((prev) => {
      const updated = [newItem, ...prev.filter((item) => item.id !== newItem.id)].slice(0, 20)
      try {
        localStorage.setItem(LOCAL_STORAGE_RECENT_KEY, JSON.stringify(updated))
      } catch {
        // localStorage unavailable (private browsing, quota) -- state
        // still updates for this session, just doesn't persist.
      }
      return updated
    })
  }, [])

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout, refresh, recentKolams, addRecentKolam }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
