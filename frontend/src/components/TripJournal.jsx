import { useEffect, useState } from 'react'
import { journalApi } from '../api/client'
import './TripJournal.css'

const emptyDraft = () => ({ title: '', content: '', occurredAt: '', mediaReferences: '' })

function parseOccurredAt(value) {
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`)
}

function toDateTimeLocal(value) {
  const date = parseOccurredAt(value)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

function draftFromEntry(entry) {
  return {
    title: entry.title || '',
    content: entry.content,
    occurredAt: toDateTimeLocal(entry.occurred_at),
    mediaReferences: (entry.media_references || []).join('\n'),
  }
}

function toPayload(draft) {
  return {
    title: draft.title.trim() || null,
    content: draft.content.trim(),
    occurred_at: draft.occurredAt ? new Date(draft.occurredAt).toISOString() : undefined,
    media_references: draft.mediaReferences.split('\n').map(value => value.trim()).filter(Boolean),
  }
}

function EntryEditor({ draft, setDraft, onSubmit, onCancel, saving, submitLabel }) {
  return <form className="journal-editor" onSubmit={onSubmit}>
    <label>Title <input maxLength="255" value={draft.title} onChange={event => setDraft(current => ({ ...current, title: event.target.value }))} placeholder="A moment worth remembering" /></label>
    <label>Entry <textarea required maxLength="10000" value={draft.content} onChange={event => setDraft(current => ({ ...current, content: event.target.value }))} placeholder="Write about this part of the trip..." /></label>
    <label>Date and time <input type="datetime-local" value={draft.occurredAt} onChange={event => setDraft(current => ({ ...current, occurredAt: event.target.value }))} /></label>
    <label>Media links <textarea value={draft.mediaReferences} onChange={event => setDraft(current => ({ ...current, mediaReferences: event.target.value }))} placeholder="One HTTP(S) link per line" /></label>
    <div className="journal-editor-actions"><button className="button button-primary" disabled={saving}>{saving ? 'Saving...' : submitLabel}</button>{onCancel && <button className="button button-quiet" type="button" onClick={onCancel}>Cancel</button>}</div>
  </form>
}

export default function TripJournal({ trip, user }) {
  const [entries, setEntries] = useState([])
  const [statistics, setStatistics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [draft, setDraft] = useState(emptyDraft)
  const [editingId, setEditingId] = useState(null)

  const refresh = async () => {
    setLoading(true)
    setError('')
    try {
      const [timeline, summary] = await Promise.all([journalApi.list(trip.id), journalApi.statistics(trip.id)])
      setEntries(timeline)
      setStatistics(summary)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([journalApi.list(trip.id), journalApi.statistics(trip.id)])
      .then(([timeline, summary]) => {
        if (active) { setEntries(timeline); setStatistics(summary) }
      })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [trip.id])

  const submit = async event => {
    event.preventDefault()
    setError('')
    setMessage('')
    setSaving(true)
    const payload = toPayload(draft)
    try {
      if (editingId) await journalApi.update(editingId, payload)
      else await journalApi.create(trip.id, payload)
      setDraft(emptyDraft())
      setEditingId(null)
      setMessage(editingId ? 'Journal entry updated.' : 'Journal entry added.')
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const edit = entry => {
    setEditingId(entry.id)
    setDraft(draftFromEntry(entry))
    setError('')
    setMessage('')
    document.getElementById('journal-editor')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const remove = async entry => {
    if (!window.confirm('Delete this journal entry? This cannot be undone.')) return
    setError('')
    setMessage('')
    try {
      await journalApi.remove(entry.id)
      setMessage('Journal entry deleted.')
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  const cancelEdit = () => { setEditingId(null); setDraft(emptyDraft()) }

  return <div className="trip-journal">
    {error && <p className="form-error" role="alert">{error}</p>}
    {message && <p className="journal-success" role="status">{message}</p>}
    <section className="journal-statistics" aria-label="Trip statistics">
      <div><strong>{statistics?.planned_duration_days ?? '—'}</strong><span>Planned days</span></div>
      <div><strong>{statistics?.journal_entry_count ?? '—'}</strong><span>Journal entries</span></div>
      <div><strong>{statistics?.journal_days_covered ?? '—'}</strong><span>Days recorded</span></div>
      <div><strong>{statistics?.media_reference_count ?? '—'}</strong><span>Media links</span></div>
      <div><strong>{statistics ? `${statistics.expense_currency} ${Number(statistics.expense_total).toLocaleString()}` : '—'}</strong><span>Recorded expenses</span></div>
    </section>
    <section className="panel journal-compose" id="journal-editor">
      <div><p className="eyebrow">Trip journal</p><h2>{editingId ? 'Edit entry' : 'Add to the journey'}</h2></div>
      <EntryEditor draft={draft} setDraft={setDraft} onSubmit={submit} onCancel={editingId ? cancelEdit : null} saving={saving} submitLabel={editingId ? 'Save changes' : 'Add entry'} />
    </section>
    <section className="journal-timeline" aria-label="Trip timeline">
      <div className="journal-heading"><div><p className="eyebrow">In order of time</p><h2>Trip timeline</h2></div>{!loading && <button className="button button-quiet" onClick={refresh}>Refresh</button>}</div>
      {loading ? <p className="page-lede" role="status">Loading your trip journal...</p>
        : entries.length === 0 ? <p className="empty-state">No journal entries yet. Add the first moment above.</p>
          : <ol className="journal-entry-list">{entries.map(entry => <li className="journal-entry" key={entry.id}>
            <time dateTime={parseOccurredAt(entry.occurred_at).toISOString()}>{parseOccurredAt(entry.occurred_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time>
            <article><div className="journal-entry-heading"><div><h3>{entry.title || 'Travel note'}</h3><p className="journal-author">By {entry.author_name}</p></div>{entry.created_by_user_id === user?.id && <div className="journal-entry-actions"><button className="button button-quiet" onClick={() => edit(entry)}>Edit</button><button className="button button-quiet" onClick={() => remove(entry)}>Delete</button></div>}</div>
              <p className="journal-content">{entry.content}</p>
              {entry.media_references.length > 0 && <ul className="journal-media">{entry.media_references.map(reference => <li key={reference}><a href={reference} target="_blank" rel="noreferrer">{reference}</a></li>)}</ul>}
            </article>
          </li>)}</ol>}
    </section>
  </div>
}