import { Component } from 'react'
import './ErrorBoundary.css'

/**
 * Root-level error boundary. Catches render errors anywhere below it and
 * shows a plain, honest fallback instead of a blank white screen -- never
 * a raw stack trace, which could leak internal file paths to end users.
 */
export default class ErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) {
      // Dev-only diagnostics; never runs in a production build.
      console.error('Unhandled render error:', error, info)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-fallback">
          <div className="error-boundary-card">
            <h1 className="error-boundary-title">Something went wrong</h1>
            <p className="error-boundary-text">
              PULLI ran into an unexpected error. Try reloading the page -- if it keeps
              happening, please let us know what you were doing when it occurred.
            </p>
            <button className="error-boundary-btn" onClick={() => window.location.reload()}>
              Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
