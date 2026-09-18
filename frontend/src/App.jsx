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
import TripDetailPage from './pages/TripDetailPage'
import ProtectedRoute from './routes/ProtectedRoute'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import PreferencesPage from './pages/PreferencesPage'
import KnowledgeCenterPage from './pages/KnowledgeCenterPage'
import TravelGuidePage from './pages/TravelGuidePage'
import AdminRoute from './routes/AdminRoute'
import InvitationAcceptPage from './pages/InvitationAcceptPage'
import './App.css'

export default function App() {
  const location = useLocation()
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register' || location.pathname === '/forgot-password'
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
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/invitations/:token" element={<InvitationAcceptPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/trips" element={<TripsPage />} />
              <Route path="/trips/:tripId" element={<TripDetailPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/preferences" element={<PreferencesPage />} />
              <Route path="/travel-guide" element={<TravelGuidePage />} />
            </Route>
            <Route element={<AdminRoute />}><Route path="/admin/knowledge" element={<KnowledgeCenterPage />} /></Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        {!isAuthPage && <Footer />}
      </div>
    </AuthProvider>
  )
}
