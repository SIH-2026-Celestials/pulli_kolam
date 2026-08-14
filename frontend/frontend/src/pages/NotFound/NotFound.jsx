import { Link } from 'react-router-dom'
import './NotFound.css'

export default function NotFound() {
  return (
    <main id="main-content" className="notfound-page">
      <div className="container notfound-content">
        <p className="eyebrow eyebrow--accent">404</p>
        <h1 className="heading-display heading-2">Page Not Found</h1>
        <p className="body-text">The page you're looking for doesn't exist or has moved.</p>
        <Link to="/" className="btn-generate-more">Return Home</Link>
      </div>
    </main>
  )
}
