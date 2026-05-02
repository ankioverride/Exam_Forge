import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './lib/auth'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import Home from './pages/Home'
import Tests from './pages/Tests'
import Configure from './pages/Configure'
import Test from './pages/Test'
import Result from './pages/Result'
import Solutions from './pages/Solutions'
import Dashboard from './pages/Dashboard'
import Bookmarks from './pages/Bookmarks'

function Layout() {
  const { pathname } = useLocation()
  const isTest = pathname.startsWith('/test/')

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {!isTest && <Navbar />}
      <div className="flex-1">
        <Routes>
          <Route path="/"           element={<Home />} />
          <Route path="/tests"             element={<Tests />} />
          <Route path="/configure/:exam"  element={<Configure />} />
          <Route path="/test/:exam"       element={<Test />} />
          <Route path="/result"     element={<Result />} />
          <Route path="/solutions"  element={<Solutions />} />
          <Route path="/dashboard"  element={<Dashboard />} />
          <Route path="/bookmarks" element={<Bookmarks />} />
        </Routes>
      </div>
      {!isTest && <Footer />}
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout />
      </AuthProvider>
    </BrowserRouter>
  )
}
