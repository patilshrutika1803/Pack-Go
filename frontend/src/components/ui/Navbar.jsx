import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const { isAuthenticated, user, logout } = useAuth()
  const close = () => setOpen(false)
  return (
    <header className="navbar">
      <Link to="/" className="logo" onClick={close}><span>✦</span> PACK &amp; GO</Link>
      <button className="menu-button" aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen(!open)}>{open ? '×' : '☰'}</button>
      <nav id="primary-navigation" className={`nav-links ${open ? 'is-open' : ''}`} onKeyDown={(event) => { if (event.key === 'Escape') close() }}>
        <NavLink to="/explore" onClick={close}>Explore</NavLink>
        <NavLink to="/plan" onClick={close}>Plan a trip</NavLink>
        <NavLink to="/trips" onClick={close}>My trips</NavLink>
        <span className="nav-divider" />
        {isAuthenticated ? <><NavLink to="/travel-guide" onClick={close}>Travel Guide</NavLink><NavLink to="/profile" onClick={close}>{user?.name || 'Profile'}</NavLink><NavLink to="/preferences" onClick={close}>Preferences</NavLink>{user?.is_admin && <><NavLink to="/admin" onClick={close}>Admin</NavLink><NavLink to="/admin/knowledge" onClick={close}>Knowledge</NavLink></>}<button className="nav-logout" onClick={() => { logout(); close() }}>Log out</button></> : <Link className="button button-small" to="/login" onClick={close}>Log in</Link>}
      </nav>
    </header>
  )
}
