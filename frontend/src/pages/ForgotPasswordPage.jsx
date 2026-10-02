import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { authApi } from '../api/client'

export default function ForgotPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const resetToken = searchParams.get('token') || ''
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setMessage('')
    setIsLoading(true)
    try {
      if (resetToken) {
        await authApi.resetPassword(resetToken, password)
        setMessage('Your password has been reset. You can now log in.')
        setTimeout(() => navigate('/login'), 800)
      } else {
        const result = await authApi.forgotPassword(email)
        setMessage(result.message + (result.development_token ? ` Development token: ${result.development_token}` : ''))
      }
    } catch (err) {
      setError(err.message || 'Unable to complete password recovery right now. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return <section className="auth-experience"><div className="auth-form-panel"><div className="auth-card"><div className="auth-card-heading"><p className="auth-card-kicker">PACK &amp; GO / ACCOUNT RECOVERY</p><h2>{resetToken ? 'Choose a new password.' : 'Forgot your password?'}</h2><p>{resetToken ? 'Set a new password for your account.' : 'Enter your email and we will generate recovery instructions.'}</p></div><form className="auth-form" onSubmit={submit}>{resetToken ? <label>New password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="8" required autoComplete="new-password" /></label> : <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>}{error && <p className="form-error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}<button className="button button-primary submit-button" disabled={isLoading}>{isLoading ? 'Loading...' : resetToken ? 'Reset password' : 'Continue'}</button></form><p className="auth-switch"><Link to="/login">Return to login</Link></p></div></div></section>
}
