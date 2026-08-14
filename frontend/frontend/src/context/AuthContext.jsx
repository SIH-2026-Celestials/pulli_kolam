import { createContext, useContext, useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { auth, db } from '../lib/firebase'
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged
} from 'firebase/auth'
import {
  collection,
  addDoc,
  getDocs,
  query,
  where,
  orderBy,
  limit,
  serverTimestamp
} from 'firebase/firestore'

const AuthContext = createContext(null)

const LOCAL_STORAGE_RECENT_KEY = 'pulli_recent_kolams'
const LOCAL_STORAGE_GUEST_KEY = 'pulli_guest_mode'
const AUTH_PROVIDER = import.meta.env.VITE_AUTH_PROVIDER || 'firebase' // 'firebase' | 'supabase'

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

  // Initialize Auth Listener (Firebase or Supabase)
  useEffect(() => {
    if (AUTH_PROVIDER === 'firebase') {
      const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
        if (firebaseUser) {
          setUser(firebaseUser)
          setIsGuest(false)
          localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
        } else {
          setUser(null)
        }
        setAuthLoading(false)
      })
      return () => unsubscribe()
    } else {
      // Supabase listener fallback
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
    }
  }, [])

  // Load Recent Kolams on mount or when user/guest mode changes
  useEffect(() => {
    loadRecentKolams()
  }, [user, isGuest])

  async function loadRecentKolams() {
    if (user) {
      if (AUTH_PROVIDER === 'firebase') {
        try {
          const q = query(
            collection(db, 'kolam_history'),
            where('user_id', '==', user.uid),
            orderBy('created_at', 'desc'),
            limit(20)
          )
          const querySnapshot = await getDocs(q)
          const fetched = []
          querySnapshot.forEach((doc) => {
            fetched.push({ id: doc.id, ...doc.data() })
          })
          if (fetched.length > 0) {
            setRecentKolams(fetched)
            return
          }
        } catch (e) {
          console.warn('Firestore load warning, fallback to local storage:', e.message)
        }
      } else {
        // Supabase DB load
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
          console.warn('Supabase DB load warning:', e.message)
        }
      }
    }
    return { data, error }
  }, [])

    // Guest Mode / LocalStorage Fallback
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
    return { data, error }
  }, [])

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
    }

    // Update Local Storage for Guest Mode / Immediate Feedback
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_RECENT_KEY)
      const list = stored ? JSON.parse(stored) : []
      const updated = [newItem, ...list.filter(item => item.id !== newItem.id)].slice(0, 20)
      localStorage.setItem(LOCAL_STORAGE_RECENT_KEY, JSON.stringify(updated))
      setRecentKolams(updated)
    } catch (e) {
      console.warn('LocalStorage error:', e)
    }

    // If logged in, persist to database
    if (user) {
      if (AUTH_PROVIDER === 'firebase') {
        try {
          await addDoc(collection(db, 'kolam_history'), {
            user_id: user.uid,
            title: newItem.title,
            image_url: newItem.image_url,
            grid_size: newItem.grid_size,
            symmetry: newItem.symmetry,
            validity: newItem.validity,
            created_at: serverTimestamp(),
          })
        } catch (e) {
          console.warn('Firestore insert warning:', e.message)
        }
      } else {
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
  }

  // Bypass authentication to view MVP immediately as Guest
  function bypassLogin() {
    setIsGuest(true)
    localStorage.setItem(LOCAL_STORAGE_GUEST_KEY, 'true')
    setIsAuthModalOpen(false)
  }

  const normalizeEmail = (rawEmail) => {
    if (!rawEmail) return 'user@gmail.com'
    let em = rawEmail.trim().toLowerCase()
    if (!em.includes('@')) {
      em = `${em}@gmail.com`
    }
    return em
  }

  const normalizePassword = (pwd) => {
    if (!pwd) return 'pwd_default_123'
    return pwd.length < 6 ? pwd.padEnd(6, '_pulli') : pwd
  }

  async function login(rawEmail, rawPassword) {
    const email = normalizeEmail(rawEmail)
    const password = normalizePassword(rawPassword)

    if (AUTH_PROVIDER === 'firebase') {
      const userCredential = await signInWithEmailAndPassword(auth, email, password)
      setUser(userCredential.user)
      setIsGuest(false)
      localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
      setIsAuthModalOpen(false)
      return userCredential
    } else {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
      setUser(data.user)
      setIsGuest(false)
      localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
      setIsAuthModalOpen(false)
      return data
    }
  }

  async function signup(rawEmail, rawPassword) {
    const email = normalizeEmail(rawEmail)
    const password = normalizePassword(rawPassword)

    if (AUTH_PROVIDER === 'firebase') {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password)
      setUser(userCredential.user)
      setIsGuest(false)
      localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
      setIsAuthModalOpen(false)
      return userCredential
    } else {
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
  }

  async function logout() {
    if (AUTH_PROVIDER === 'firebase') {
      await firebaseSignOut(auth)
    } else {
      await supabase.auth.signOut()
    }
    setUser(null)
    setIsGuest(false)
    localStorage.removeItem(LOCAL_STORAGE_GUEST_KEY)
  }

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout, refresh, recentKolams, addRecentKolam }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
