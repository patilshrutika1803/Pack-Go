import './MessageBubble.css'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`bubble-row ${isUser ? 'user' : 'assistant'} fade-in-up`}>
      <div className="bubble-avatar">
        {isUser ? '👤' : '✈️'}
      </div>
      <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
        <p>{message.content}</p>
        {message.sources?.length > 0 && <div className="source-list"><small>Sources</small>{message.sources.map((source) => <details className="source-card" key={`${source.document_id}-${source.page}-${source.chunk_index}`}><summary>{source.filename} · Page {source.page}</summary><span>{source.destination} · {source.category}</span><p>{source.preview}</p></details>)}</div>}
      </div>
    </div>
  )
}
