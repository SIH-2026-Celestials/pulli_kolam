import { createContext, useContext, useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext()

const LOCAL_STORAGE_RECENT_KEY = 'pulli_recent_kolams'
const LOCAL_STORAGE_GUEST_KEY = 'pulli_guest_mode'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isGuest, setIsGuest] = useState(() => {
    return localStorage.getItem(LOCAL_STORAGE_GUEST_KEY) === 'true'
  })
  const [authLoading, setAuthLoading] = useState(true)
  const [recentKolams, setRecentKolams] = useState([])
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)

  // Initialize Supabase Auth Session
  useEffect(() => {
    async function initAuth() {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        if (session?.user) {
          setUser(session.user)
          setIsGuest(false)
          localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
        }
      } catch (err) {
        console.warn('Supabase auth init warning:', err.message)
      } finally {
        setAuthLoading(false)
      }
    }

    initAuth()

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setUser(session.user)
        setIsGuest(false)
        localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
      } else {
        setUser(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  // Load Recent Kolams on mount or when user/guest mode changes
  useEffect(() => {
    loadRecentKolams()
  }, [user, isGuest])

  async function loadRecentKolams() {
    if (user) {
      // Authenticated User: Load from Supabase DB table
      try {
        const { data, error } = await supabase
          .from('kolam_history')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(20)

        if (!error && data) {
          setRecentKolams(data)
          return
        }
      } catch (e) {
        console.warn('Supabase DB load warning, fallback to local storage:', e.message)
      }
    }

    // Unauthenticated / Guest Mode: Load from LocalStorage
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_RECENT_KEY)
      if (stored) {
        setRecentKolams(JSON.parse(stored))
      } else {
        setRecentKolams([])
      }
    } catch (e) {
      setRecentKolams([])
    }
  }

  // Add a newly generated or analyzed Kolam to recent history
  async function addRecentKolam(kolamItem) {
    const newItem = {
      id: kolamItem.id || `kolam_${Date.now()}`,
      title: kolamItem.title || 'Generated Pulli Kolam',
      image_url: kolamItem.image_url || kolamItem.imagePath || '/static/synthetic/kolam19_1.jpg',
      grid_size: kolamItem.grid_size || '7×7',
      symmetry: kolamItem.symmetry || 'D4 Dihedral',
      validity: kolamItem.validity || '✓ Eulerian Single-stroke',
      created_at: new Date().toISOString(),
      is_guest: !user,
    }

    // Update Local Storage for Guest Mode / Fallback
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_RECENT_KEY)
      const list = stored ? JSON.parse(stored) : []
      const updated = [newItem, ...list.filter(item => item.id !== newItem.id)].slice(0, 20)
      localStorage.setItem(LOCAL_STORAGE_RECENT_KEY, JSON.stringify(updated))
      setRecentKolams(updated)
    } catch (e) {
      console.warn('LocalStorage error:', e)
    }

    // If logged in, also persist to Supabase database
    if (user) {
      try {
        await supabase.from('kolam_history').insert([
          {
            user_id: user.id,
            title: newItem.title,
            image_url: newItem.image_url,
            grid_size: newItem.grid_size,
            symmetry: newItem.symmetry,
            validity: newItem.validity,
          }
        ])
      } catch (e) {
        console.warn('Supabase insert warning:', e.message)
      }
    }
  }

  // Bypass authentication to view MVP immediately as Guest
  function bypassLogin() {
    setIsGuest(true)
    localStorage.setItem(LOCAL_STORAGE_GUEST_KEY, 'true')
    setIsAuthModalOpen(false)
  }

  async function login(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    setUser(data.user)
    setIsGuest(false)
    localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
    setIsAuthModalOpen(false)
    return data
  }

  async function signup(email, password) {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
    if (data?.user) {
      setUser(data.user)
      setIsGuest(false)
      localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
    }
    setIsAuthModalOpen(false)
    return data
  }

  async function logout() {
    await supabase.auth.signOut()
    setUser(null)
    setIsGuest(false)
    localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isGuest,
        authLoading,
        recentKolams,
        isAuthModalOpen,
        setIsAuthModalOpen,
        bypassLogin,
        login,
        signup,
        logout,
        addRecentKolam,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
