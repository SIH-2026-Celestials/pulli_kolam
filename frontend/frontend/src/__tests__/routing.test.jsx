import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import Footer from '../components/Footer/Footer'
import { LanguageProvider } from '../context/LanguageContext'
import { AuthProvider } from '../context/AuthContext'
import { AuthModalProvider } from '../context/AuthModalContext'

// Every path App.jsx registers a <Route> for. Kept in sync manually --
// if this list drifts from App.jsx, the "renders without crashing" cases
// below stop being representative.
const STATIC_ROUTES = [
  '/', '/project', '/how-it-works', '/explore', '/analyze',
  '/detect', '/playground', '/learn', '/technology', '/impact', '/about',
  '/login', '/register', '/account', '/privacy', '/terms', '/contact',
  '/this-route-does-not-exist',
]

// /playground renders real <canvas> 2D drawing, which jsdom can't
// simulate without the native `canvas` package -- excluded from the
// generic smoke-render list below, not because the route is untested,
// but because this specific gap is an environment limitation, not app code.
const SMOKE_ROUTES = STATIC_ROUTES.filter((r) => r !== '/playground')

function withProviders(children) {
  return (
    <LanguageProvider>
      <AuthProvider>
        <AuthModalProvider>
          {children}
        </AuthModalProvider>
      </AuthProvider>
    </LanguageProvider>
  )
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      {withProviders(<App />)}
    </MemoryRouter>
  )
}

describe('App routing', () => {
  it.each(SMOKE_ROUTES)('renders %s without crashing', (path) => {
    renderAt(path)
    expect(screen.getAllByRole('banner').length).toBeGreaterThan(0)
  })

  it('renders a kolam detail page for a known id', () => {
    renderAt('/explore/26')
    expect(screen.getAllByRole('banner').length).toBeGreaterThan(0)
  })
})

describe('Footer links', () => {
  it('only links to routes App.jsx actually registers', () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Footer />
        </LanguageProvider>
      </MemoryRouter>
    )
    const links = screen.queryAllByRole('link').map((a) => a.getAttribute('href'))
    for (const href of links) {
      expect(STATIC_ROUTES).toContain(href)
    }
  })
})
