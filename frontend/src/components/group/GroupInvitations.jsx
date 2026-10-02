export function GroupInvitations({ invitations, revokeInvitation }) {
	const copyLink = invitation => { const token = invitation.token || sessionStorage.getItem(`pack-go-invitation-${invitation.id}`); if (token) navigator.clipboard?.writeText(`${window.location.origin}/invitations/${token}`) }
	return <section className="panel group-invitations">
		<header className="group-section-heading"><div><p className="eyebrow">Bring people along</p><h2>Invitations</h2><p>Manage shared links and see their current status.</p></div></header>
		{invitations.length === 0 && <p className="empty-state">No invitations yet. Generate a link from the members list to invite someone to this group.</p>}
		<div className="invitation-list">{invitations.map(invitation => <article className={`invitation-card invitation-${invitation.status}`} key={invitation.id}>
			<div className="invitation-details"><span className="invitation-icon" aria-hidden="true">↗</span><div><strong>Group invitation</strong><p>Expires {new Date(invitation.expires_at).toLocaleDateString()}</p></div></div>
			<span className={`status-pill status-${invitation.status}`}>{invitation.status}</span>
			{invitation.status === 'pending' && <div className="inline-actions"><button className="button button-quiet" onClick={() => copyLink(invitation)} disabled={!invitation.token && !sessionStorage.getItem(`pack-go-invitation-${invitation.id}`)}>Copy invite link</button><button className="button button-quiet" onClick={() => revokeInvitation(invitation.id)}>Revoke invitation</button></div>}
		</article>)}</div>
	</section>
}
