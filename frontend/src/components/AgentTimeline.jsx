import './AgentTimeline.css'

const AGENT_META = {
  Supervisor:          { icon: '🧭', label: 'Supervisor' },
  PreferenceExtractor: { icon: '💡', label: 'Preference Extractor' },
  ResearchAgent:       { icon: '🔍', label: 'Research Agent' },
  WeatherAgent:        { icon: '☀️', label: 'Weather Agent' },
  BudgetAgent:         { icon: '💰', label: 'Budget Agent' },
  ItineraryAgent:      { icon: '🗺️', label: 'Itinerary Agent' },
  CriticAgent:         { icon: '⭐', label: 'Critic Agent' },
}

export default function AgentTimeline({ agents, currentAgent, allAgents, loading }) {
  return (
    <div className="timeline">
      <p className="timeline-title">Agent Pipeline</p>
      <div className="timeline-list">
        {allAgents.map((name, idx) => {
          const done    = agents.includes(name)
          const active  = currentAgent === name
          const pending = !done && !active
          const meta    = AGENT_META[name] || { icon: '🤖', label: name }

          return (
            <div
              key={name}
              className={`timeline-item ${done ? 'done' : ''} ${active ? 'active' : ''} ${pending ? 'pending' : ''}`}
              style={{ animationDelay: `${idx * 0.06}s` }}
            >
              {/* Connector line */}
              {idx < allAgents.length - 1 && (
                <div className={`timeline-connector ${done ? 'done' : ''}`} />
              )}

              <div className="timeline-dot">
                {done ? (
                  <svg width="10" height="10" viewBox="0 0 12 12">
                    <path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                  </svg>
                ) : active ? (
                  <span className="dot-pulse" />
                ) : (
                  <span className="dot-empty" />
                )}
              </div>

              <div className="timeline-label">
                <span className="tl-icon">{meta.icon}</span>
                <span className="tl-name">{meta.label}</span>
                {active && <span className="tl-badge">Running</span>}
              </div>
            </div>
          )
        })}
      </div>

      {!loading && agents.length === 0 && (
        <p className="timeline-idle">Waiting for query…</p>
      )}
    </div>
  )
}
