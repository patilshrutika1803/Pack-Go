import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function AdminRoute() {
  const { isAuthenticated, isLoading, user } = useAuth()
  const location = useLocation()
  if (isLoading) return <div className="route-loading">Checking access…</div>
  if (!isAuthenticated) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  return user?.is_admin ? <Outlet /> : <Navigate to="/" replace />
}