import { Routes, Route } from 'react-router-dom'
import Header from './components/Header/Header'
import Footer from './components/Footer/Footer'
import AuthModal from './components/AuthModal/AuthModal'
import Home from './pages/Home/Home'
import Project from './pages/Project/Project'
import HowItWorks from './pages/HowItWorks/HowItWorks'
import Explore from './pages/Explore/Explore'
import KolamDetail from './pages/KolamDetail/KolamDetail'
import Analyze from './pages/Analyze/Analyze'
import Detect from './pages/Detect/Detect'
import Playground from './pages/Playground/Playground'
import Learn from './pages/Learn/Learn'
import LearnModule from './pages/Learn/LearnModule'
import Technology from './pages/Technology/Technology'
import Impact from './pages/Impact/Impact'
import About from './pages/About/About'
import Login from './pages/Login/Login'
import Register from './pages/Register/Register'
import Account from './pages/Account/Account'
import Privacy from './pages/Privacy/Privacy'
import Terms from './pages/Terms/Terms'
import Contact from './pages/Contact/Contact'
import NotFound from './pages/NotFound/NotFound'
import KolamGridPattern from './components/kolam/KolamGridPattern'
import TamilCultureBackground from './components/kolam/TamilCultureBackground'
import TamilParallaxGopuram from './components/kolam/TamilParallaxGopuram'
import './styles/global.css'

export default function App() {
  return (
    <div className="app-shell">
      <TamilParallaxGopuram />
      <TamilCultureBackground />
      <KolamGridPattern opacity={0.015} />
      <Header />
      <AuthModal />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/project" element={<Project />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/explore/:id" element={<KolamDetail />} />
        <Route path="/analyze" element={<Analyze />} />
        <Route path="/detect" element={<Detect />} />
        <Route path="/playground" element={<Playground />} />
        <Route path="/learn" element={<Learn />} />
        <Route path="/learn/:moduleSlug" element={<LearnModule />} />
        <Route path="/technology" element={<Technology />} />
        <Route path="/impact" element={<Impact />} />
        <Route path="/about" element={<About />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/account" element={<Account />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Footer />
    </div>
  )
}
