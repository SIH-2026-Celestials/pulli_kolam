import { Routes, Route } from 'react-router-dom'
import Header from './components/Header/Header'
import Footer from './components/Footer/Footer'
import Home from './pages/Home/Home'
import Project from './pages/Project/Project'
import HowItWorks from './pages/HowItWorks/HowItWorks'
import Explore from './pages/Explore/Explore'
import KolamDetail from './pages/KolamDetail/KolamDetail'
import Analyze from './pages/Analyze/Analyze'
import Detect from './pages/Detect/Detect'
import Learn from './pages/Learn/Learn'
import LearnModule from './pages/Learn/LearnModule'
import Technology from './pages/Technology/Technology'
import Impact from './pages/Impact/Impact'
import About from './pages/About/About'
import NotFound from './pages/NotFound/NotFound'
import './styles/global.css'

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/project" element={<Project />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/explore" element={<Explore />} />
        <Route path="/explore/:id" element={<KolamDetail />} />
        <Route path="/analyze" element={<Analyze />} />
        
        <Route path="/detect" element={<Detect />} />
        <Route path="/learn" element={<Learn />} />
        <Route path="/learn/:moduleSlug" element={<LearnModule />} />
        <Route path="/technology" element={<Technology />} />
        <Route path="/impact" element={<Impact />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Footer />
    </div>
  )
}
