import { useState, useEffect } from 'react'
import './HeroSection.css'

const SUGGESTIONS = [
  '3 day budget trip to Goa under ₹20,000',
  '5 day luxury trip to Rajasthan',
  'Weekend getaway to Coorg for 2',
  '7 day backpacking trip across Himachal Pradesh',
]

export default function HeroSection({ onSubmit, loading }) {
  const [typed, setTyped]   = useState('')
  const [phrase, setPhrase] = useState(0)
  const [input, setInput]   = useState('')

  // Typewriter effect on subtitle
  useEffect(() => {
    const target = SUGGESTIONS[phrase % SUGGESTIONS.length]
    let i = 0
    setTyped('')
    const interval = setInterval(() => {
      if (i < target.length) {
        setTyped(target.slice(0, ++i))
      } else {
        clearInterval(interval)
        setTimeout(() => setPhrase(p => p + 1), 2200)
      }
    }, 38)
    return () => clearInterval(interval)
  }, [phrase])

  const handleKey = (e) => {
    if (e.key === 'Enter' && input.trim()) onSubmit(input)
  }

  return (
    <div className="hero-wrapper">
      <div className="hero-content fade-in-up">
        {/* Globe animation */}
        <div className="hero-globe" aria-hidden>🌍</div>

        <h1 className="hero-title">
          Plan your <span className="gradient-text">perfect journey</span>
          <br />with AI.
        </h1>

        <p className="hero-subtitle">
          One Platform for Every Journey
        </p>

        {/* Main input */}
        <div className="hero-input-wrap">
          <input
            className="hero-input"
            type="text"
            placeholder="Where do you want to travel?"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            autoFocus
            disabled={loading}
          />
          <button
            className="hero-btn"
            onClick={() => input.trim() && onSubmit(input)}
            disabled={loading || !input.trim()}
          >
            {loading ? (
              <span className="hero-spinner" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>
        </div>

        {/* Quick suggestion chips */}
        <div className="hero-chips">
          {SUGGESTIONS.slice(0, 3).map((s, i) => (
            <button
              key={i}
              className="hero-chip"
              onClick={() => onSubmit(s)}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Feature pills */}
      <div className="hero-features fade-in">
        {['🤖 Multi-Agent AI', '📊 Budget-Aware', '☁️ Live Weather', '⚡ Real-time Streaming'].map(f => (
          <div key={f} className="feature-pill">{f}</div>
        ))}
      </div>
    </div>
  )
}
