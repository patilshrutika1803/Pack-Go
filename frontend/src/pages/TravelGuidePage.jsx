import { useEffect, useMemo, useRef, useState } from 'react'
import ChatInput from '../components/ChatInput'
import MessageBubble from '../components/MessageBubble'
import { knowledgeApi } from '../api/client'

const EMPTY_FILTERS = { search: '', destination: '', category: '', document_type: '' }

export default function TravelGuidePage() {
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [documents, setDocuments] = useState([])
  const [loadState, setLoadState] = useState('loading')
  const [error, setError] = useState('')
  const [messages, setMessages] = useState([])
  const [asking, setAsking] = useState(false)
  const requestId = useRef(0)

  useEffect(() => {
    const currentRequest = ++requestId.current
    const timer = setTimeout(async () => {
      setLoadState('loading')
      setError('')
      try {
        const result = await knowledgeApi.userList(filters)
        if (currentRequest === requestId.current) {
          setDocuments(result)
          setLoadState('ready')
        }
      } catch (requestError) {
        if (currentRequest === requestId.current) {
          setError(requestError.message)
          setLoadState('error')
        }
      }
    }, 250)
    return () => clearTimeout(timer)
  }, [filters])

  const options = useMemo(() => ({
    destination: [...new Set(documents.map((document) => document.destination).filter(Boolean))],
    category: [...new Set(documents.map((document) => document.category).filter(Boolean))],
    document_type: [...new Set(documents.map((document) => document.document_type).filter(Boolean))],
  }), [documents])

  const updateFilter = (event) => setFilters((current) => ({ ...current, [event.target.name]: event.target.value }))
  const resetFilters = () => setFilters(EMPTY_FILTERS)

  const askQuestion = async (question) => {
    setAsking(true)
    setMessages((current) => [...current, { role: 'user', content: question, id: `${Date.now()}-question` }])
    try {
      const answer = await knowledgeApi.ask({
        question,
        destination: filters.destination || undefined,
        category: filters.category || undefined,
        document_type: filters.document_type || undefined,
      })
      setMessages((current) => [...current, {
        role: 'assistant',
        content: answer.answer,
        sources: answer.sources || [],
        id: `${Date.now()}-answer`,
      }])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAsking(false)
    }
  }

  return <section className="travel-guide-page page-container">
    <header className="travel-guide-heading">
      <div>
        <p className="eyebrow">PACK &amp; GO knowledge base</p>
        <h1>Travel<br /><em>Guide</em></h1>
        <p>Browse indexed destination guidance and ask questions answered from PACK &amp; GO&apos;s travel knowledge base.</p>
      </div>
      <div className="travel-guide-stat"><strong>{documents.length}</strong><span>available sources</span></div>
    </header>

    {error && <div className="knowledge-message travel-guide-error" role="alert">{error}</div>}

    <div className="travel-guide-layout">
      <div className="travel-guide-browse">
        <div className="knowledge-list-heading"><div><p className="eyebrow">Browse sources</p><h2>Destination notes</h2></div><button className="button button-quiet" onClick={resetFilters}>Clear filters</button></div>
        <div className="travel-guide-filters">
          <label className="travel-guide-search">Search by document name<input name="search" value={filters.search} onChange={updateFilter} placeholder="Search the guide" /></label>
          {['destination', 'category', 'document_type'].map((field) => <label key={field}>{field.replace('_', ' ')}<select name={field} value={filters[field]} onChange={updateFilter}><option value="">All {field.replace('_', ' ')}s</option>{options[field].map((option) => <option key={option} value={option}>{option}</option>)}</select></label>)}
        </div>
        {loadState === 'loading' && <div className="knowledge-empty">Loading travel sources…</div>}
        {loadState === 'error' && <div className="knowledge-empty"><strong>Sources could not be loaded.</strong><button className="text-button" onClick={() => setFilters({ ...filters })}>Try again</button></div>}
        {loadState === 'ready' && !documents.length && <div className="knowledge-empty">No sources match those filters.</div>}
        {loadState === 'ready' && documents.map((document) => <article className="travel-guide-card" key={document.id}>
          <div className="travel-guide-card-top"><span className="knowledge-mark">SOURCE</span><span className={`knowledge-status knowledge-status-${document.status}`}>{document.status}</span></div>
          <h3>{document.display_name}</h3>
          <p className="travel-guide-card-meta">{document.destination} · {document.category} · {document.document_type}</p>
          <small>{document.page_count} pages · {document.chunk_count} knowledge chunks</small>
        </article>)}
      </div>

      <section className="travel-guide-ask">
        <div className="knowledge-list-heading"><div><p className="eyebrow">Grounded Q&amp;A</p><h2>Ask PACK &amp; GO</h2></div><span className="travel-guide-ask-mark">RAG</span></div>
        <p className="travel-guide-ask-intro">Ask about the indexed sources. Answers stay within the available evidence and show the sources used.</p>
        <div className="travel-guide-chat">{!messages.length && <div className="travel-guide-chat-empty">Try a focused question about a destination, activity, season, or route.</div>}{messages.map((message) => <MessageBubble key={message.id} message={message} />)}{asking && <div className="travel-guide-thinking">Checking the travel knowledge base…</div>}</div>
        <ChatInput onSubmit={askQuestion} loading={asking} compact />
      </section>
    </div>
  </section>
}