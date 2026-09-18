import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { invitationsApi } from '../api/client'
import { useAuth } from '../auth/useAuth'

export default function InvitationAcceptPage() {
  const { token } = useParams()
  const { isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const [state, setState] = useState('loading')
  const [invitation, setInvitation] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    invitationsApi.preview(token).then(result => { setInvitation(result); setState('ready') }).catch(err => { setError(err.message); setState('error') })
  }, [token])

  const accept = () => invitationsApi.accept(token)
    .then(result => { setState('accepted'); navigate(`/trips/${result.trip_id}?tab=overview`, { replace: true }) })
    .catch(err => { setError(err.message); setState('error') })

  if (state === 'loading') return <section className="page-container placeholder"><p className="eyebrow">PACK &amp; GO</p><h1>Checking your invitation...</h1></section>
  if (state === 'error') return <section className="page-container placeholder"><p className="eyebrow">PACK &amp; GO</p><h1>Invitation unavailable</h1><p className="form-error" role="alert">{error || 'This invitation is no longer active.'}</p><Link className="button button-primary" to="/trips">Go to my trips</Link></section>
  if (invitation.status !== 'pending') return <section className="page-container placeholder"><p className="eyebrow">PACK &amp; GO</p><h1>{invitation.status === 'expired' ? 'This invitation has expired.' : invitation.status === 'revoked' ? 'This invitation is no longer active.' : 'This invitation has already been accepted.'}</h1><Link className="button button-primary" to="/trips">Go to my trips</Link></section>
  if (state === 'accepted') return <section className="page-container placeholder"><p className="eyebrow">PACK &amp; GO</p><h1>Invitation accepted.</h1></section>
  const invitationPath = `/invitations/${token}`
  return <section className="page-container placeholder invitation-page"><p className="eyebrow">PACK &amp; GO</p><h1>You&apos;re invited to join {invitation.trip_title}</h1><div className="invitation-details"><p><strong>Destination:</strong> {invitation.destination}</p><p><strong>Trip duration:</strong> {invitation.duration} days</p><p><strong>Group members:</strong> {invitation.member_count}</p><p>Expires {new Date(invitation.expires_at).toLocaleDateString()}</p></div>{isLoading ? <p>Checking your account...</p> : isAuthenticated ? <button className="button button-primary" onClick={accept}>Join group</button> : <div className="inline-actions"><p>Log in to join this group.</p><Link className="button button-primary" to={`/login?next=${encodeURIComponent(invitationPath)}`}>Log in</Link><Link className="button button-quiet" to={`/register?next=${encodeURIComponent(invitationPath)}`}>Create account</Link></div>}</section>
}
