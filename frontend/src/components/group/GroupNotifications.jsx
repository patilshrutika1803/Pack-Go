export function GroupNotifications({ notifications, readAll, read, openNotification, loading, error }) {
	const unreadCount = notifications.filter(item => !item.read_at).length
	return <section className="panel group-notifications">
		<header className="group-section-heading"><div><p className="eyebrow">Stay up to date</p><h2>Notifications</h2><p>{unreadCount ? `${unreadCount} unread update${unreadCount === 1 ? '' : 's'}` : 'You are all caught up.'}</p></div><button className="button button-quiet" onClick={readAll}>Mark all read</button></header>
		{loading && <p className="chat-state" role="status">Loading notifications...</p>}
		{error && <p className="form-error" role="alert">{error}</p>}
		{!loading && notifications.length === 0 && <p className="empty-state">Nothing new here. Group updates will appear in this list.</p>}
		<div className="notification-list">{notifications.map(item => <article className={`notification-card${item.read_at ? ' is-read' : ' is-unread'}`} key={item.id}>
			<span className="notification-indicator" aria-hidden="true" />
			<div className="notification-copy"><strong>{item.event_type}</strong><small>{new Date(item.created_at).toLocaleString()}</small></div>
			<div className="notification-actions">{!item.read_at && <button className="button button-quiet" onClick={() => read(item.id)}>Mark read</button>}{item.trip_id && <button className="button button-quiet" onClick={() => openNotification(item)}>Open</button>}</div>
		</article>)}</div>
	</section>
}
