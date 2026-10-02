import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/client'

const unavailableLabel = (metric) => metric?.available ? 'Available' : 'Unavailable'

export default function AdminDashboardPage() {
  const [overview, setOverview] = useState(null)
  const [state, setState] = useState('loading')
  const [message, setMessage] = useState('')

  const loadOverview = useCallback(async () => {
    setState('loading')
    setMessage('')
    try {
      setOverview(await adminApi.overview())
      setState('ready')
    } catch (error) {
      setMessage(error.message)
      setState('error')
    }
  }, [])

  useEffect(() => { loadOverview() }, [loadOverview])

  if (state === 'loading') return <section className="page-container"><p className="eyebrow">Admin workspace</p><h1>Loading overview</h1></section>
  if (state === 'error') return <section className="page-container"><p className="eyebrow">Admin workspace</p><h1>Overview unavailable</h1><p>{message}</p><button className="button button-primary" onClick={loadOverview}>Try again</button></section>

  const { analytics, system } = overview
  return <section className="page-container">
    <div className="knowledge-heading"><div><p className="eyebrow">Admin workspace</p><h1>Platform<br /><em>Overview</em></h1><p>Operational counts from the current PACK &amp; GO database.</p></div><button className="button button-quiet" onClick={loadOverview}>Refresh</button></div>
    <div className="knowledge-layout">
      <div className="knowledge-list">
        <div className="knowledge-list-heading"><div><p className="eyebrow">Analytics</p><h2>Supported metrics</h2></div></div>
        <div className="knowledge-form-grid">
          <div><strong>{analytics.total_users}</strong><p>Total users</p></div>
          <div><strong>{analytics.total_trips}</strong><p>Total trips</p></div>
          <div><strong>{analytics.group_trips}</strong><p>Group trips</p></div>
          <div><strong>{analytics.expense_count}</strong><p>Expense records</p></div>
          <div><strong>{analytics.journal_entry_count}</strong><p>Journal entries</p></div>
          <div><strong>{analytics.expense_total.toFixed(2)}</strong><p>Recorded expenses</p></div>
        </div>
        <div className="knowledge-list-heading"><div><p className="eyebrow">Destinations</p><h2>Trip distribution</h2></div></div>
        {!analytics.destinations.length && <div className="knowledge-empty">No trips have been recorded.</div>}
        {analytics.destinations.map((item) => <article className="knowledge-document" key={item.destination}><div><h3>{item.destination}</h3><p>{item.trip_count} trip{item.trip_count === 1 ? '' : 's'}</p></div></article>)}
      </div>
      <aside className="knowledge-upload"><div className="section-title-row"><h2>System status</h2><span className="knowledge-status knowledge-status-indexed">{system.database}</span></div><p>Knowledge sources: {system.knowledge.total_sources}</p><p>Indexed: {system.knowledge.indexed_sources}</p><p>Processing: {system.knowledge.processing_sources}</p><p>Failed: {system.knowledge.failed_sources}</p><hr /><h2>Unavailable telemetry</h2><p>Active users: {unavailableLabel(analytics.active_users)}</p><p>AI requests: {unavailableLabel(analytics.ai_requests)}</p><p>Agent usage: {unavailableLabel(analytics.agent_usage)}</p><p>Provider usage: {unavailableLabel(analytics.provider_usage)}</p></aside>
    </div>
  </section>
}