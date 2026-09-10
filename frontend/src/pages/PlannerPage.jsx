import { useState, useRef, useEffect } from 'react'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'
import PlanCard from '../components/PlanCard'
import HeroSection from '../components/HeroSection'
import { useAuth } from '../auth/useAuth'

const AGENT_ORDER = ['Supervisor', 'PreferenceExtractor', 'ResearchAgent', 'WeatherAgent', 'BudgetAgent', 'ItineraryAgent', 'CriticAgent']

export default function PlannerPage() {
  const { token } = useAuth()
  const [messages, setMessages] = useState([]); const [agents, setAgents] = useState([]); const [currentAgent, setCurrentAgent] = useState(null); const [plan, setPlan] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(null); const bottomRef = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, plan])
  const handleSubmit = async (query) => {
    if (!query.trim() || loading) return
    setLoading(true); setError(null); setPlan(null); setAgents([]); setCurrentAgent(null); setMessages(prev => [...prev, { role: 'user', content: query, id: Date.now() }])
    try { const response = await fetch('/plan/stream', { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ question: query, thread_id: crypto.randomUUID(), remember_me: true }) }); if (!response.ok) throw new Error('Unable to start your plan.')
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
      while (true) { const { value, done } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n\n'); buffer = lines.pop(); for (const chunk of lines) { const line = chunk.trim(); if (!line.startsWith('data: ')) continue; try { const event = JSON.parse(line.slice(6)); const { status, agent, message, data } = event; if (status === 'running' && agent && agent !== 'System') { setCurrentAgent(agent); setAgents(prev => prev.includes(agent) ? prev : [...prev, agent]) } if (status === 'done') { setCurrentAgent(null); setPlan(data); setLoading(false) } if (status === 'error') { setError(message); setLoading(false) } } catch { /* Ignore incomplete SSE chunks. */ } } }
    } catch (err) { setError(err.message); setLoading(false) }
  }
  return <div className="planner-shell"><main className="planner-main">{!messages.length ? <HeroSection onSubmit={handleSubmit} loading={loading} /> : <><div className="chat-area"><div className="planner-breadcrumb">Plan a trip <span>/</span> Your next journey</div>{messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}{loading && <div className="generation-panel fade-in"><div className="generation-heading"><span className="generation-orb" /><div><p className="eyebrow">PACK &amp; GO AI</p><h2>Planning your journey</h2></div></div><AgentTimelineCompact agents={agents} currentAgent={currentAgent} allAgents={AGENT_ORDER} /></div>}{error && <div className="error-banner fade-in-up">{error}</div>}{plan && !loading && <div className="fade-in-up"><PlanCard plan={plan} /></div>}<div ref={bottomRef} /></div><div className="input-footer"><ChatInput onSubmit={handleSubmit} loading={loading} compact /></div></>}</main></div>
}

function AgentTimelineCompact({ agents, currentAgent, allAgents }) {
  const labels = { Supervisor: 'Understanding your preferences', PreferenceExtractor: 'Understanding your preferences', ResearchAgent: 'Researching places', WeatherAgent: 'Checking weather', BudgetAgent: 'Building your budget', ItineraryAgent: 'Creating your itinerary', CriticAgent: 'Reviewing the plan' }
  return <div className="compact-agent-list">{allAgents.slice(1).map((agent) => { const done = agents.includes(agent); const active = currentAgent === agent; return <div className={`compact-agent ${done ? 'done' : ''} ${active ? 'active' : ''}`} key={agent}><span className="compact-agent-dot">{done ? '✓' : active ? '•' : '○'}</span><span>{labels[agent]}</span></div> })}</div>
}
