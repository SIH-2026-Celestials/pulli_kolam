import { createContext, useContext, useState, useCallback } from 'react'

const AuthModalContext = createContext(null)

export function AuthModalProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false)
  const [mode, setMode] = useState('login') // 'login' | 'register'

  const openLogin = useCallback(() => {
    setMode('login')
    setIsOpen(true)
  }, [])

  const openRegister = useCallback(() => {
    setMode('register')
    setIsOpen(true)
  }, [])

  const closeModal = useCallback(() => {
    setIsOpen(false)
  }, [])

  const toggleMode = useCallback(() => {
    setMode(m => (m === 'login' ? 'register' : 'login'))
  }, [])

  return (
    <AuthModalContext.Provider
      value={{
        isOpen,
        mode,
        openLogin,
        openRegister,
        closeModal,
        toggleMode,
        setMode
      }}
    >
      {children}
    </AuthModalContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuthModal() {
  const ctx = useContext(AuthModalContext)
  if (!ctx) {
    throw new Error('useAuthModal must be used within an AuthModalProvider')
  }
  return ctx
}
