import { getMessageSenderLabel } from './groupDisplay'

export function GroupChat({ messages, draft, setDraft, sendMessage, editMessage, deleteMessage, loadOlder, hasMore, loading, error, canChat = true, userId, canModerate = false }) {
	return <section className="panel group-chat">
		<header className="group-section-heading"><div><p className="eyebrow">Keep everyone in the loop</p><h2>Group chat</h2><p>A shared conversation for the trip.</p></div></header>
		{!canChat && <p className="chat-permission" role="status">You no longer have permission to use this chat.</p>}
		{loading && <p className="chat-state" role="status">Loading messages...</p>}
		{error && <p className="form-error" role="alert">{error}</p>}
		{canChat && hasMore && <button className="button button-quiet chat-load-older" onClick={loadOlder}>Load older messages</button>}
		{canChat && !loading && messages.length === 0 && <p className="empty-state chat-state">No messages yet. Start the conversation with your group.</p>}
		{canChat && messages.length > 0 && <div className="chat-message-list" aria-label="Group messages">
			{messages.map(item => <article className={`chat-message${item.sender_user_id === userId ? ' chat-message-own' : ''}`} key={item.id}>
				<div className="chat-message-heading"><strong>{getMessageSenderLabel(item)}{item.sender_user_id === userId && <span>You</span>}</strong><small>{new Date(item.created_at).toLocaleString()}{item.edited_at && ' · edited'}</small></div>
				<p>{item.deleted_at ? 'Message deleted' : item.body}</p>
				{!item.deleted_at && (item.sender_user_id === userId || canModerate) && <div className="chat-message-actions"><button className="button button-quiet" onClick={() => editMessage(item)}>Edit</button><button className="button button-quiet" onClick={() => deleteMessage(item.id)}>Delete</button></div>}
			</article>)}
		</div>}
		{canChat && <form className="chat-composer" onSubmit={event => { event.preventDefault(); sendMessage() }}><input value={draft} onChange={event => setDraft(event.target.value)} placeholder="Write a message" aria-label="Chat message" /><button className="button button-primary" type="submit">Send</button></form>}
	</section>
}
