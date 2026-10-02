import { useState } from 'react'

export function GroupProposals({ proposals, results, createProposal, vote, removeVote, finalize, close, updateProposal, canManage }) {
	const [type, setType] = useState('other')
	const [form, setForm] = useState({ title: '', destination: '', name: '', day_number: '1', meal_index: '0', activity_index: '0', item_index: '0', value: '' })
	const updateForm = event => setForm({ ...form, [event.target.name]: event.target.value })
	const submit = event => {
		event.preventDefault()
		const payload = { value: form.value }
		if (type === 'destination') payload.destination = form.destination
		if (['hotel', 'restaurant', 'activity', 'itinerary_item'].includes(type)) payload.day_number = Number(form.day_number)
		if (type === 'restaurant') payload.meal_index = Number(form.meal_index)
		if (type === 'activity') payload.activity_index = Number(form.activity_index)
		if (type === 'itinerary_item') payload.item_index = Number(form.item_index)
		if (['hotel', 'restaurant', 'activity'].includes(type)) payload.name = form.name
		createProposal({ proposal_type: type, title: form.title, payload })
		setForm({ ...form, title: '', value: '' })
	}
	return <section className="panel group-proposals">
		<header className="group-section-heading"><div><p className="eyebrow">Decide together</p><h2>Proposals</h2><p>Share an idea, cast your vote, and see where the group stands.</p></div></header>
		{proposals.length === 0 && <p className="empty-state">No proposals yet. Create the first one to get the group’s input.</p>}
		{proposals.map(proposal => {
			const result = results[proposal.id]
			const tied = result?.ties?.length > 1
			return <article className="proposal-card" key={proposal.id}>
				<div className="proposal-heading"><div><h3>{proposal.title}</h3><p>{proposal.description || 'Open for votes'}</p></div><span className={`status-pill status-${proposal.status}`}>{proposal.status}</span></div>
				{proposal.deadline && <p className="proposal-deadline">Voting closes {new Date(proposal.deadline).toLocaleString()}</p>}
				{result && <div className="proposal-results" aria-label={`Results for ${proposal.title}`}>
					<div className="proposal-result-heading"><strong>Current results</strong><span className="proposal-your-vote">Your vote: <b>{result.user_vote || 'Not voted'}</b></span></div>
					{Object.entries(result.counts).length ? <div className="proposal-choice-list">{Object.entries(result.counts).map(([choice, count]) => <div className={`proposal-choice${result.user_vote === choice ? ' is-your-vote' : ''}${result.winner === choice ? ' is-winner' : ''}`} key={choice}><span>{choice}{result.user_vote === choice && <small>Your vote</small>}</span><strong>{count} {count === 1 ? 'vote' : 'votes'}</strong></div>)}</div> : <p className="proposal-no-votes">No votes yet.</p>}
					{tied && <p className="proposal-outcome">Tie between {result.ties.join(', ')}</p>}
					{!tied && result.winner && <p className="proposal-outcome">Leading choice: {result.winner}</p>}
				</div>}
				{proposal.status === 'open' && <>
					<form className="proposal-vote-form" onSubmit={event => {
						event.preventDefault()
						const voteForm = event.currentTarget
						const choice = voteForm.elements.choice.value.trim()
						if (choice) vote(proposal.id, choice).then(() => voteForm.reset())
					}}>
						<input name="choice" aria-label={`Vote for ${proposal.title}`} placeholder="Enter your choice" required />
						<button className="button button-primary" type="submit">Submit vote</button>
					</form>
					<button className="button button-quiet proposal-remove-vote" onClick={() => removeVote(proposal.id)}>Remove my vote</button>
				</>}
				{canManage && proposal.status === 'open' && <div className="proposal-manage-actions">
					<button className="button button-quiet" onClick={() => close(proposal.id)}>Close</button>
					<button className="button button-quiet" onClick={() => updateProposal(proposal)}>Edit</button>
					<button className="button button-primary" onClick={() => finalize(proposal.id)}>Finalize</button>
				</div>}
			</article>
		})}
		<form className="proposal-create-form" onSubmit={submit}>
			<div><p className="eyebrow">New idea</p><h3>Create a proposal</h3><p>Put an option to the group for a quick vote.</p></div>
			<select value={type} onChange={event => setType(event.target.value)}><option value="destination">Destination</option><option value="hotel">Hotel</option><option value="restaurant">Restaurant</option><option value="activity">Activity</option><option value="itinerary_item">Itinerary item</option><option value="other">Other</option></select>
			<input name="title" value={form.title} onChange={updateForm} placeholder="Proposal title" required />
			{type === 'destination' && <input name="destination" value={form.destination} onChange={updateForm} placeholder="Destination" required />}
			{type !== 'destination' && type !== 'other' && <>
				<input name="name" value={form.name} onChange={updateForm} placeholder="Name" />
				<input name="day_number" type="number" min="1" value={form.day_number} onChange={updateForm} />
				{type === 'restaurant' && <input name="meal_index" type="number" min="0" value={form.meal_index} onChange={updateForm} />}
				{type === 'activity' && <input name="activity_index" type="number" min="0" value={form.activity_index} onChange={updateForm} />}
				{type === 'itinerary_item' && <input name="item_index" type="number" min="0" value={form.item_index} onChange={updateForm} />}
			</>}
			<textarea name="value" value={form.value} onChange={updateForm} placeholder="Proposed details" required />
			<button className="button button-primary" type="submit">Create proposal</button>
		</form>
	</section>
}
