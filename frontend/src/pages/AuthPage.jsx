import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { authApi } from '../api/client'

export default function AuthPage({ mode }) {
  const isRegister = mode === 'register'
  const { login, register, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [verificationToken, setVerificationToken] = useState('')
  const [verificationMessage, setVerificationMessage] = useState('')
  const [loginMode, setLoginMode] = useState('user')
  const requestedNext = new URLSearchParams(location.search).get('next')
  const next = requestedNext?.startsWith('/') && !requestedNext.startsWith('//') ? requestedNext : '/trips'
  const update = (event) => setForm({ ...form, [event.target.name]: event.target.value })
  const switchPath = (path) => `${path}${location.search}`
  const safeError = (message) => {
    if (!isRegister) return "Email or password doesn't look right. Please try again."
    if (/already exists/i.test(message || '')) return 'An account with this email already exists.'
    return message || 'Unable to create your account right now. Please try again.'
  }
  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (isRegister && form.password !== form.confirmPassword) return setError('Passwords do not match.')
    if (form.password.length < 8) return setError('Use at least 8 characters for your password.')
    try {
      const result = await (isRegister ? register(form) : login({ email: form.email, password: form.password }))
      if (isRegister && result.verification_token) {
        setVerificationToken(result.verification_token)
        setVerificationMessage('Account created. Verify your email before continuing.')
      } else if (loginMode === 'admin' && !result.user?.is_admin) {
        setError('This account does not have administrator access.')
      } else {
        navigate(loginMode === 'admin' ? '/admin/knowledge' : next, { replace: true })
      }
    } catch (err) {
      setError(safeError(err.message))
    }
  }

  return (
    <section className="auth-experience">
      <div className="auth-brand-panel">
        <Link to="/" className="auth-logo"><span>✦</span> PACK &amp; GO</Link>
        <div className="auth-brand-copy">
          <p className="auth-eyebrow"><span>YOUR NEXT ADVENTURE</span><i /></p>
          <h1>Plan smarter.<br /><em>Travel further.</em></h1>
          <p>From a rough idea to a trip worth taking, PACK &amp; GO helps you plan the journey around what matters to you.</p>
        </div>
        <div className="auth-destinations" aria-label="Featured destinations">
          <article className="auth-destination auth-destination-goa"><div><strong>Goa</strong><span>Coastal escape</span></div></article>
          <article className="auth-destination auth-destination-rajasthan"><div><strong>Rajasthan</strong><span>Culture &amp; colour</span></div></article>
          <article className="auth-destination auth-destination-coorg"><div><strong>Coorg</strong><span>Into the green</span></div></article>
        </div>
        <div className="auth-feature-pills"><span>AI trip planning</span><span>Smart itinerary</span><span>Budget-aware</span><span>Live weather</span></div>
        <p className="auth-brand-footer">Travel farther. Plan lighter.</p>
      </div>

      <div className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-card-heading">
            <p className="auth-card-kicker">PACK &amp; GO / {isRegister ? 'NEW TRAVELLER' : 'WELCOME BACK'}</p>
            <h2>{isRegister ? 'Create your account.' : 'Good to see you.'}</h2>
            <p>{isRegister ? "Let's get you ready for your next journey." : 'Your next adventure starts here.'}</p>
          </div>
          {!isRegister && <div className="auth-mode-selector" role="group" aria-label="Sign-in access mode">
            <button type="button" className={loginMode === 'user' ? 'is-active' : ''} onClick={() => { setLoginMode('user'); setError('') }}>User</button>
            <button type="button" className={loginMode === 'admin' ? 'is-active' : ''} onClick={() => { setLoginMode('admin'); setError('') }}>Admin</button>
          </div>}
          <div className={`auth-tabs${!isRegister && loginMode === 'admin' ? ' auth-tabs-single' : ''}`} role="tablist" aria-label="Authentication mode">
            <Link className={!isRegister ? 'is-active' : ''} to={switchPath('/login')} role="tab" aria-selected={!isRegister}>Log in</Link>
            {(isRegister || loginMode === 'user') && <Link className={isRegister ? 'is-active' : ''} to={switchPath('/register')} role="tab" aria-selected={isRegister}>Sign up</Link>}
          </div>
          <form className="auth-form" onSubmit={submit}>
            {isRegister && <label>Full name<input name="name" value={form.name} onChange={update} autoComplete="name" required placeholder="Your name" /></label>}
            <label>Email<input name="email" type="email" value={form.email} onChange={update} autoComplete="email" required placeholder="you@example.com" /></label>
            <label>Password<div className="auth-password-field"><input name="password" type={showPassword ? 'text' : 'password'} value={form.password} onChange={update} autoComplete={isRegister ? 'new-password' : 'current-password'} required placeholder="At least 8 characters" /><button className="password-toggle" type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}><span className={showPassword ? 'eye-icon is-open' : 'eye-icon'} /></button></div></label>
            {isRegister && <label>Confirm password<input name="confirmPassword" type={showPassword ? 'text' : 'password'} value={form.confirmPassword} onChange={update} autoComplete="new-password" required placeholder="Type it again" /></label>}
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary submit-button" disabled={isLoading}>{isLoading ? 'Loading...' : isRegister ? 'Create account →' : 'Log in →'}</button>
          </form>
          {isRegister && verificationToken && <div className="auth-form-meta"><span>{verificationMessage}</span><button type="button" className="text-button" onClick={async () => { try { await authApi.verifyEmail(verificationToken); setVerificationMessage('Email verified successfully.'); navigate(next, { replace: true }) } catch (err) { setError(err.message || 'Unable to verify your email right now. Please try again.') } }}>Verify email</button></div>}
          {!isRegister && <>
            <div className="auth-form-meta"><span>Secure access to your trips</span><Link className="auth-link-muted" to="/forgot-password">Forgot password?</Link></div>
            <div className="auth-divider"><span>OR</span></div>
            <button className="button google-button" type="button" disabled><span className="google-mark">G</span> Continue with Google <small>Coming soon</small></button>
          </>}
          <p className="auth-switch">{isRegister ? 'Already have an account?' : "Don't have an account?"} <Link to={switchPath(isRegister ? '/login' : '/register')}>{isRegister ? 'Log in' : 'Create one'}</Link></p>
        </div>
      </div>
    </section>
  )
}
