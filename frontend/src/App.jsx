import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import Navbar from './components/ui/Navbar'
import Footer from './components/ui/Footer'
import LandingPage from './pages/LandingPage'
import AuthPage from './pages/AuthPage'
import PlannerPage from './pages/PlannerPage'
import ExplorePage from './pages/ExplorePage'
import TripsPage from './pages/TripsPage'
import ProfilePage from './pages/ProfilePage'
import ProtectedRoute from './routes/ProtectedRoute'
import './App.css'

export default function App() {
  const location = useLocation()
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register'
  return (
    <AuthProvider>
      <div className="site-shell">
        {!isAuthPage && <Navbar />}
        <main className="site-main">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/plan" element={<PlannerPage />} />
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/trips" element={<TripsPage />} />
              <Route path="/trips/:tripId" element={<TripsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        {!isAuthPage && <Footer />}
      </div>
    </AuthProvider>
  )
}
