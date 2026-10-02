export function GroupMembers({ workspace, user, invite, leave, transfer, updateMember, removeMember }) {
	const current = workspace.members.find(member => member.user_id === user?.id)
	return <section className="panel group-members">
		<header className="group-section-heading">
			<div><p className="eyebrow">Your travel crew</p><h2>Members</h2><p>{workspace.member_count} active member{workspace.member_count === 1 ? '' : 's'}</p></div>
			{['owner', 'admin'].includes(current?.role) && <button className="button button-primary" onClick={invite}>Generate invite link</button>}
		</header>
		<div className="member-list">
			{workspace.members.map(member => {
				const name = member.user?.name || member.user_id
				const isCurrentUser = member.user_id === user?.id
				return <article className="member-card" key={member.id}>
					<div className="member-identity">
						<span className="member-avatar" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
						<div><strong>{name}{isCurrentUser && <span className="member-you">You</span>}</strong><small>{member.user?.email || ''}</small></div>
					</div>
					<div className="member-meta">
						<span className={`member-role member-role-${member.role}`}>{member.role}</span>
						<span className={`member-status member-status-${member.status || 'active'}`}>{member.status || 'active'}</span>
					</div>
					<div className="member-actions">
						{isCurrentUser && member.role !== 'owner' && <button className="button button-quiet" onClick={leave}>Leave group</button>}
						{current?.role === 'owner' && member.user_id !== user.id && <>
							<label className="sr-only" htmlFor={`member-role-${member.id}`}>Role for {name}</label>
							<select id={`member-role-${member.id}`} value={member.role} onChange={event => updateMember(member.user_id, event.target.value)}><option value="member">Member</option><option value="admin">Admin</option></select>
							<button className="button button-quiet member-remove" onClick={() => removeMember(member.user_id)}>Remove</button>
						</>}
					</div>
				</article>
			})}
		</div>
		{current?.role === 'owner' && <div className="ownership-control">
			<div><strong>Transfer ownership</strong><p>Choose another member to make them the group owner.</p></div>
			<select id="ownership-target" defaultValue="" aria-label="Transfer ownership to" onChange={event => event.target.value && transfer(event.target.value)}><option value="">Select a member</option>{workspace.members.filter(member => member.user_id !== user.id).map(member => <option key={member.user_id} value={member.user_id}>{member.user?.name || member.user_id}</option>)}</select>
		</div>}
	</section>
}
