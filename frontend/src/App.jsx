import { useState, useRef, useEffect } from 'react'
import AgentTimeline from './components/AgentTimeline'
import ChatInput from './components/ChatInput'
import MessageBubble from './components/MessageBubble'
import PlanCard from './components/PlanCard'
import HeroSection from './components/HeroSection'
import './App.css'

const AGENT_ORDER = [
  'Supervisor',
  'PreferenceExtractor',
  'ResearchAgent',
  'WeatherAgent',
  'BudgetAgent',
  'ItineraryAgent',
  'CriticAgent',
]

export default function App() {
  const [messages, setMessages]     = useState([])       // chat history
  const [agents, setAgents]         = useState([])        // completed agents
  const [currentAgent, setCurrentAgent] = useState(null)  // currently running
  const [plan, setPlan]             = useState(null)      // final plan data
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)
  const bottomRef                   = useRef(null)

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, plan])

  const handleSubmit = async (query) => {
    if (!query.trim() || loading) return

    // Reset state for new query
    setLoading(true)
    setError(null)
    setPlan(null)
    setAgents([])
    setCurrentAgent(null)

    const userMsg = { role: 'user', content: query, id: Date.now() }
    setMessages(prev => [...prev, userMsg])

    const threadId = crypto.randomUUID()

    try {
      const response = await fetch('/plan/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: query, thread_id: threadId, remember_me: true }),
      })

      if (!response.ok) throw new Error(`API error: ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() // keep incomplete chunk

        for (const chunk of lines) {
          const line = chunk.trim()
          if (!line.startsWith('data: ')) continue

          try {
            const event = JSON.parse(line.slice(6))
            const { status, agent, message, data } = event

            if (status === 'running' && agent && agent !== 'System') {
              setCurrentAgent(agent)
              setAgents(prev =>
                prev.includes(agent) ? prev : [...prev, agent]
              )
            }

            if (status === 'done') {
              setCurrentAgent(null)
              setAgents(AGENT_ORDER)
              setPlan(data)
              setLoading(false)
            }

            if (status === 'error') {
              setError(message)
              setLoading(false)
            }
          } catch (_) { /* skip malformed event */ }
        }
      }
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const hasConversation = messages.length > 0

  return (
    <div className="app-shell">
      {/* ── Left Sidebar: Agent Timeline ── */}
      <aside className="sidebar glass">
        <div className="sidebar-brand">
          <span className="brand-icon">✈️</span>
          <span className="brand-name">PACK & GO</span>
          <span className="brand-version">v2.0</span>
        </div>

        <AgentTimeline
          agents={agents}
          currentAgent={currentAgent}
          allAgents={AGENT_ORDER}
          loading={loading}
        />

        {plan?.budget && (
          <div className="sidebar-budget">
            <p className="sidebar-budget-label">Trip Budget Used</p>
            <div className="budget-bar-track">
              <div
                className="budget-bar-fill"
                style={{
                  width: `${Math.min(100, (plan.budget.total_estimated / (plan.preferences?.total_budget || plan.budget.total_estimated)) * 100)}%`
                }}
              />
            </div>
            <div className="budget-bar-values">
              <span>₹{plan.budget.total_estimated?.toLocaleString()}</span>
              <span className="text-muted">/ ₹{plan.preferences?.total_budget?.toLocaleString()}</span>
            </div>
          </div>
        )}
      </aside>

      {/* ── Main Content ── */}
      <main className="main-content">
        {!hasConversation ? (
          <HeroSection onSubmit={handleSubmit} loading={loading} />
        ) : (
          <>
            <div className="chat-area">
              {messages.map(msg => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {loading && (
                <div className="thinking-indicator fade-in">
                  <div className="thinking-dots">
                    <span /><span /><span />
                  </div>
                  <span className="thinking-text">
                    {currentAgent ? `${currentAgent} is working...` : 'Initializing agents...'}
                  </span>
                </div>
              )}

              {error && (
                <div className="error-banner fade-in-up">
                  <span>⚠️</span> {error}
                </div>
              )}

              {plan && !loading && (
                <div className="fade-in-up">
                  <PlanCard plan={plan} />
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            <div className="input-footer">
              <ChatInput onSubmit={handleSubmit} loading={loading} compact />
            </div>
          </>
        )}
      </main>
      <div className="app-footer">Powered by PACK & GO</div>
    </div>
  )
}
