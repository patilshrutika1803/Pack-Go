import { useState } from 'react'
import './HeroSection.css'

export default function HeroSection({ onSubmit, loading }) {
  const [input, setInput]   = useState('')

  const handleKey = (e) => {
    if (e.key === 'Enter' && input.trim()) onSubmit(input)
  }

  return (
    <div className="hero-wrapper">
      <div className="hero-content fade-in-up">
        {/* Globe animation */}
        <div className="planner-kicker"><span>01</span> A little planning goes a long way</div>

        <h1 className="hero-title">
          Where are you <em>going?</em>
        </h1>

        <p className="hero-subtitle">
          Tell us what you have in mind. PACK &amp; GO will build the rest.
        </p>

        {/* Main input */}
        <div className="hero-input-wrap">
          <input
            className="hero-input"
            type="text"
            placeholder="Try: 3 days in Goa for two under ₹20,000"
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
        <div className="suggestion-grid">
          {['Weekend in Goa', '5 days in Rajasthan', 'Budget trip to Himachal', '3 days in Coorg'].map((s, i) => (
            <button
              key={i}
              className="suggestion-card"
              onClick={() => onSubmit(s)}
              disabled={loading}
            >
              <span className="suggestion-number">0{i + 1}</span><strong>{s}</strong><span aria-hidden>↗</span>
            </button>
          ))}
        </div>
      </div>

      {/* Feature pills */}
      <div className="hero-features fade-in">
        {['AI itinerary', 'Budget planning', 'Live weather', 'Smart recommendations'].map((f, i) => (
          <div key={f} className={`feature-pill feature-pill-${i}`}>{f}</div>
        ))}
      </div>
    </div>
  )
}
