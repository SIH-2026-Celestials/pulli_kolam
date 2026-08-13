import { Link } from 'react-router-dom'
import './Footer.css'

export default function Footer() {
  return (
    <footer className="footer-clone">
      <div className="footer-inner">
        <div className="footer-left">
          <span>&copy; 2024 PULLI &ndash; Kolam Design-Principle Engine</span>
        </div>

        <div className="footer-center">
          <span>AICTE &ndash; Heritage &amp; Culture Initiative</span>
        </div>

        <div className="footer-right">
          <Link to="/privacy" className="footer-link">Privacy Policy</Link>
          <Link to="/terms" className="footer-link">Terms of Use</Link>
          <Link to="/contact" className="footer-link">Contact</Link>
        </div>
      </div>

      {/* Decorative Bottom Pattern Overlay */}
      <div className="footer-pattern">
        <svg width="100%" height="10" viewBox="0 0 1200 10" preserveAspectRatio="none" fill="none">
          <path d="M 0 5 Q 15 0 30 5 Q 45 10 60 5 Q 75 0 90 5 Q 105 10 120 5 Q 135 0 150 5 Q 165 10 180 5 Q 195 0 210 5 Q 225 10 240 5 Q 255 0 270 5 Q 285 10 300 5 Q 315 0 330 5 Q 345 10 360 5 Q 375 0 390 5 Q 405 10 420 5 Q 435 0 450 5 Q 465 10 480 5 Q 495 0 510 5 Q 525 10 540 5 Q 555 0 570 5 Q 585 10 600 5 Q 615 0 630 5 Q 645 10 660 5 Q 675 0 690 5 Q 705 10 720 5 Q 735 0 750 5 Q 765 10 780 5 Q 795 0 810 5 Q 825 10 840 5 Q 855 0 870 5 Q 885 10 900 5 Q 915 0 930 5 Q 945 10 960 5 Q 975 0 990 5 Q 1005 10 1020 5 Q 1035 0 1050 5 Q 1065 10 1080 5 Q 1095 0 1110 5 Q 1125 10 1140 5 Q 1155 0 1170 5 Q 1185 10 1200 5" stroke="#B88735" strokeWidth="0.8" opacity="0.3" />
        </svg>
      </div>
    </footer>
  )
}
