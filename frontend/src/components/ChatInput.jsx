import { useState } from 'react'
import './ChatInput.css'

export default function ChatInput({ onSubmit, loading, compact }) {
  const [value, setValue] = useState('')

  const submit = () => {
    if (value.trim() && !loading) {
      onSubmit(value)
      setValue('')
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className={`chat-input-wrap ${compact ? 'compact' : ''}`}>
      <input
        className="chat-input"
        type="text"
        placeholder="Ask another trip question…"
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKey}
        disabled={loading}
      />
      <button className="chat-send-btn" onClick={submit} disabled={loading || !value.trim()}>
        {loading ? (
          <span className="send-spinner" />
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )}
      </button>
    </div>
  )
}
