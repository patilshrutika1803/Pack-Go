import { useState, useRef, useEffect } from 'react'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'
import PlanCard from '../components/PlanCard'
import HeroSection from '../components/HeroSection'
import { useAuth } from '../auth/useAuth'

const AGENT_ORDER = ['Supervisor', 'PreferenceExtractor', 'ResearchAgent', 'WeatherAgent', 'BudgetAgent', 'ItineraryAgent', 'CriticAgent']

export default function PlannerPage() {
  const { token } = useAuth()
  const [messages, setMessages] = useState([]); const [agentStatuses, setAgentStatuses] = useState({}); const [currentAgent, setCurrentAgent] = useState(null); const [plan, setPlan] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState(null); const bottomRef = useRef(null); const streamController = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, plan])
  useEffect(() => () => streamController.current?.abort(), [])
  const handleSubmit = async (query) => {
    if (!query.trim() || loading) return
    setLoading(true); setError(null); setPlan(null); setAgentStatuses({}); setCurrentAgent(null); setMessages(prev => [...prev, { role: 'user', content: query, id: Date.now() }])
    const controller = new AbortController()
    streamController.current = controller
    try { const response = await fetch('/plan/stream', { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ question: query, thread_id: crypto.randomUUID(), remember_me: true }), signal: controller.signal }); if (!response.ok) throw new Error('Unable to start your plan.')
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
      let receivedTerminalEvent = false
      while (true) { const { value, done } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n\n'); buffer = lines.pop(); for (const chunk of lines) { const line = chunk.trim(); if (!line.startsWith('data: ')) continue; try { const event = JSON.parse(line.slice(6)); const { status, agent, message, data } = event; if (status === 'agent_started' && agent) { setCurrentAgent(agent); setAgentStatuses(prev => ({ ...prev, [agent]: 'working' })) } if (['agent_completed', 'agent_fallback', 'agent_error'].includes(status) && agent) { const nextStatus = status === 'agent_completed' ? 'completed' : status === 'agent_fallback' ? 'fallback' : 'error'; setAgentStatuses(prev => ({ ...prev, [agent]: nextStatus })); setCurrentAgent(current => current === agent ? null : current) } if (status === 'done') { receivedTerminalEvent = true; setCurrentAgent(null); if (data?.intent === 'general_chat') { setMessages(prev => [...prev, { role: 'assistant', content: data.response || '', sources: data.sources || [], id: Date.now() }]) } else setPlan(data); setLoading(false) } if (status === 'error') { receivedTerminalEvent = true; setCurrentAgent(null); setError(message); setLoading(false) } } catch { /* Ignore incomplete SSE chunks. */ } } }
      if (!receivedTerminalEvent) throw new Error('The planning connection ended before a result was received. Please try again.')
    } catch (err) { if (err.name !== 'AbortError') { setCurrentAgent(null); setError(err.message); setLoading(false) } }
    finally { if (streamController.current === controller) streamController.current = null }
  }
  return <div className="planner-shell"><main className="planner-main">{!messages.length ? <HeroSection onSubmit={handleSubmit} loading={loading} /> : <><div className="chat-area"><div className="planner-breadcrumb">Plan a trip <span>/</span> Your next journey</div>{messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}{loading && <div className="generation-panel fade-in"><div className="generation-heading"><span className="generation-orb" /><div><p className="eyebrow">PACK &amp; GO AI</p><h2>Planning your journey</h2></div></div><AgentTimelineCompact agentStatuses={agentStatuses} currentAgent={currentAgent} allAgents={AGENT_ORDER} /></div>}{error && <div className="error-banner fade-in-up" role="alert">{error}</div>}{plan && !loading && <div className="fade-in-up"><PlanCard plan={plan} /></div>}<div ref={bottomRef} /></div><div className="input-footer"><ChatInput onSubmit={handleSubmit} loading={loading} compact /></div></>}</main></div>
}

function AgentTimelineCompact({ agentStatuses, currentAgent, allAgents }) {
  const labels = { Supervisor: 'Supervisor Agent', PreferenceExtractor: 'Preference Agent', ResearchAgent: 'Research Agent', WeatherAgent: 'Weather Agent', BudgetAgent: 'Budget Agent', ItineraryAgent: 'Itinerary Agent', CriticAgent: 'Critic Agent', ChatAgent: 'Travel Q&A Agent' }
  return <div className="compact-agent-list">{allAgents.map(agent => {
    const status = agentStatuses[agent] || 'pending'
    const active = currentAgent === agent
    const indicator = status === 'completed' ? '✓' : status === 'working' ? '⟳' : status === 'fallback' ? '!' : status === 'error' ? '×' : '○'
    const detail = status === 'working' ? ' — working...' : status === 'fallback' ? ' — fallback data used' : status === 'error' ? ' — could not complete' : ''
    return <div className={`compact-agent ${status === 'completed' ? 'done' : ''} ${active ? 'active' : ''} ${status === 'error' ? 'failed' : ''}`} key={agent} aria-current={active ? 'step' : undefined}><span className="compact-agent-dot">{indicator}</span><span>{labels[agent]}{detail}</span></div>
  })}</div>
}
