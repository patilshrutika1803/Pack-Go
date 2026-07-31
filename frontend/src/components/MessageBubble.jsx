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
      </div>
    </div>
  )
}
