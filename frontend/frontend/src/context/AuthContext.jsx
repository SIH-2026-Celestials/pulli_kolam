import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister } from '../lib/api/kolam'

const AuthContext = createContext(null)

const LOCAL_STORAGE_RECENT_KEY = 'pulli_recent_kolams'
const LOCAL_STORAGE_BYPASS_KEY = 'pulli_auth_bypass'

const GUEST_BYPASS_USER = {
  id: 'guest_bypass_user',
  displayName: 'Guest Explorer',
  email: 'guest@pulli-kolam.dev',
  role: 'guest',
  isBypass: true,
}

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
    try {
      if (localStorage.getItem(LOCAL_STORAGE_BYPASS_KEY) === 'true') {
        setUser(GUEST_BYPASS_USER)
        setStatus('authenticated')
        return
      }
    } catch {
      // localStorage read error fallback
    }

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

  const bypassAuth = useCallback(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_BYPASS_KEY, 'true')
    } catch {
      // localStorage write error fallback
    }
    setUser(GUEST_BYPASS_USER)
    setStatus('authenticated')
  }, [])

  const login = useCallback(async (email, password) => {
    try {
      localStorage.removeItem(LOCAL_STORAGE_BYPASS_KEY)
    } catch {
      // ignore
    }
    const { data, error } = await apiLogin({ email, password })
    if (data) {
      setUser(data)
      setStatus('authenticated')
    }
    return { data, error }
  }, [])

  const register = useCallback(async (email, password, displayName) => {
    try {
      localStorage.removeItem(LOCAL_STORAGE_BYPASS_KEY)
    } catch {
      // ignore
    }
    const { data, error } = await apiRegister({ email, password, displayName })
    if (data) {
      setUser(data)
      setStatus('authenticated')
    }
    return { data, error }
  }, [])

  const logout = useCallback(async () => {
    try {
      localStorage.removeItem(LOCAL_STORAGE_BYPASS_KEY)
    } catch {
      // ignore
    }
    await apiLogout()
    setUser(null)
    setStatus('unauthenticated')
  }, [])

  // Local, device-scoped history of generated/analyzed Kolams. There is
  // no backend table for this (unlike users/sessions in api/auth/) --
  // it deliberately stays client-side only, same scope as the theme/
  // language preferences already kept in localStorage elsewhere.
  const addRecentKolam = useCallback((kolamItem) => {
    // No fallback values for grid_size/symmetry/validity: these are
    // real, measured properties of a specific generation. A caller that
    // omits one genuinely doesn't have that data yet -- claiming a
    // default like "D4 Dihedral" would misrepresent an unmeasured
    // pattern as having a specific, verified symmetry.
    const newItem = {
      id: kolamItem.id || `kolam_${Date.now()}`,
      title: kolamItem.title || 'Generated Pulli Kolam',
      image_url: kolamItem.image_url || kolamItem.imagePath || null,
      grid_size: kolamItem.grid_size || 'Not available',
      symmetry: kolamItem.symmetry || 'Not available',
      validity: kolamItem.validity || 'Not available',
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
    <AuthContext.Provider value={{ status, user, login, register, logout, bypassAuth, refresh, recentKolams, addRecentKolam }}>
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
