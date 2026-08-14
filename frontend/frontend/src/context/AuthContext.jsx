import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister } from '../lib/api/kolam'

const AuthContext = createContext(null)

// 'loading' | 'authenticated' | 'unauthenticated' | 'error'
// 'error' is distinct from 'unauthenticated' -- a 401 from /me genuinely
// means "no session," but a network failure means "we don't know," and
// those should not be presented to the user identically.
export function AuthProvider({ children }) {
  const [status, setStatus] = useState('loading')
  const [user, setUser] = useState(null)

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
    refresh()
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

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout, refresh }}>
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
