import { useEffect, useState } from 'react'
import { knowledgeApi } from '../api/client'

const EMPTY_FORM = { display_name: '', destination: '', category: 'travel_guide', document_type: 'destination_guide' }

export default function KnowledgeCenterPage() {
  const [documents, setDocuments] = useState([])
  const [filters, setFilters] = useState({ search: '', destination: '', category: '', document_type: '' })
  const [form, setForm] = useState(EMPTY_FORM)
  const [file, setFile] = useState(null)
  const [state, setState] = useState('loading')
  const [message, setMessage] = useState('')
  const [busyId, setBusyId] = useState(null)

  const loadDocuments = async () => {
    setState('loading')
    try {
      setDocuments(await knowledgeApi.list(filters))
      setState('ready')
    } catch (error) {
      setMessage(error.message)
      setState('error')
    }
  }

  useEffect(() => { loadDocuments() }, [])

  const updateFilter = (event) => setFilters((current) => ({ ...current, [event.target.name]: event.target.value }))
  const updateForm = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }))

  const upload = async (event) => {
    event.preventDefault()
    if (!file) return setMessage('Choose a PDF before uploading.')
    const payload = new FormData()
    payload.append('file', file)
    Object.entries(form).forEach(([key, value]) => payload.append(key, value))
    setState('uploading'); setMessage('')
    try {
      await knowledgeApi.upload(payload)
      setForm(EMPTY_FORM); setFile(null); event.target.reset(); setMessage('Document indexed successfully.'); await loadDocuments()
    } catch (error) { setMessage(error.message); setState('error') }
  }

  const reindex = async (id) => {
    setBusyId(id); setMessage('')
    try { await knowledgeApi.reindex(id); setMessage('Document re-indexed successfully.'); await loadDocuments() }
    catch (error) { setMessage(error.message) }
    finally { setBusyId(null) }
  }

  const remove = async (document) => {
    if (!window.confirm(`Delete ${document.display_name}? This also removes its indexed chunks.`)) return
    setBusyId(document.id); setMessage('')
    try { await knowledgeApi.remove(document.id); setMessage('Document deleted.'); await loadDocuments() }
    catch (error) { setMessage(error.message) }
    finally { setBusyId(null) }
  }

  return <section className="knowledge-page page-container">
    <div className="knowledge-heading"><div><p className="eyebrow">Admin workspace</p><h1>Knowledge<br /><em>Center</em></h1><p>Manage the travel documents that ground PACK &amp; GO answers.</p></div><div className="knowledge-stat"><strong>{documents.length}</strong><span>indexed sources</span></div></div>
    {message && <div className="knowledge-message" role="status">{message}</div>}
    <div className="knowledge-layout">
      <form className="knowledge-upload" onSubmit={upload}><div className="section-title-row"><h2>Upload source</h2><span className="knowledge-mark">PDF</span></div><label>PDF file<input type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label><label>Display name<input name="display_name" value={form.display_name} onChange={updateForm} required placeholder="Goa Travel Guide" /></label><div className="knowledge-form-grid"><label>Destination<input name="destination" value={form.destination} onChange={updateForm} required placeholder="Goa" /></label><label>Category<input name="category" value={form.category} onChange={updateForm} required /></label><label>Document type<input name="document_type" value={form.document_type} onChange={updateForm} required /></label></div><button className="button button-primary" disabled={state === 'uploading'}>{state === 'uploading' ? 'Indexing…' : 'Upload and index'}</button></form>
      <div className="knowledge-list"><div className="knowledge-list-heading"><div><p className="eyebrow">Document library</p><h2>Indexed sources</h2></div><button className="button button-quiet" onClick={loadDocuments} disabled={state === 'loading'}>Refresh</button></div><div className="knowledge-filters"><input name="search" value={filters.search} onChange={updateFilter} placeholder="Search documents" /><input name="destination" value={filters.destination} onChange={updateFilter} placeholder="Destination" /><input name="category" value={filters.category} onChange={updateFilter} placeholder="Category" /><button className="button button-small" onClick={loadDocuments}>Filter</button></div>{state === 'loading' && <div className="knowledge-empty">Loading sources…</div>}{state === 'error' && <div className="knowledge-empty"><strong>Sources could not be loaded.</strong><button className="text-button" onClick={loadDocuments}>Try again</button></div>}{state === 'ready' && !documents.length && <div className="knowledge-empty">No indexed documents yet.</div>}{state === 'ready' && documents.map((document) => <article className="knowledge-document" key={document.id}><div><div className="knowledge-document-title"><h3>{document.display_name}</h3><span className={`knowledge-status knowledge-status-${document.status}`}>{document.status}</span></div><p>{document.filename} · {document.destination} · {document.category}</p><small>{document.page_count} pages · {document.chunk_count} chunks</small></div><div className="knowledge-actions"><button className="text-button" disabled={busyId === document.id} onClick={() => reindex(document.id)}>Re-index</button><button className="text-button danger" disabled={busyId === document.id} onClick={() => remove(document)}>Delete</button></div></article>)}</div>
    </div>
  </section>
}