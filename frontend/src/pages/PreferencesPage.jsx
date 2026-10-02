import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { preferencesApi } from '../api/client'

const DEFAULTS = { travel_style: '', interests: [], budget_preference: '', hotel_preference: '', food_preference: '', preferred_destinations: [] }
const INTERESTS = ['Beach', 'Food', 'Culture', 'Nature', 'Adventure', 'Wellness', 'Nightlife']

export default function PreferencesPage() {
  const [form, setForm] = useState(DEFAULTS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    preferencesApi.get()
      .then((preferences) => setForm({ ...DEFAULTS, ...preferences, interests: preferences.interests || [], preferred_destinations: preferences.preferred_destinations || [] }))
      .catch((err) => setError(err.message || 'Unable to load preferences.'))
      .finally(() => setLoading(false))
  }, [])

  const setValue = (name, value) => setForm((current) => ({ ...current, [name]: value }))
  const toggleInterest = (interest) => setValue('interests', form.interests.includes(interest) ? form.interests.filter((item) => item !== interest) : [...form.interests, interest])
  const save = async (event) => {
    event.preventDefault(); setSaving(true); setMessage(''); setError('')
    try { await preferencesApi.update(form); setMessage('Preferences saved.') }
    catch (err) { setError(err.message || 'Unable to save preferences.') }
    finally { setSaving(false) }
  }

  return <section className="preferences-page page-container">
    <div className="profile-heading"><p className="eyebrow">Your travel identity</p><h1>Preferences</h1><p>Set the details you want PACK &amp; GO to remember when it plans your next trip.</p></div>
    {loading ? <p className="text-muted">Loading preferences...</p> : <form className="preferences-form" onSubmit={save}>
      <div className="preference-form-grid">
        <label>Travel style<select value={form.travel_style} onChange={(event) => setValue('travel_style', event.target.value)}><option value="">Choose a style</option><option>Relaxation</option><option>Balanced</option><option>Adventure</option><option>Luxury</option><option>Budget</option></select></label>
        <label>Budget preference<select value={form.budget_preference} onChange={(event) => setValue('budget_preference', event.target.value)}><option value="">Choose a budget</option><option>Budget</option><option>Moderate</option><option>Luxury</option><option>Flexible</option></select></label>
        <label>Hotel preference<select value={form.hotel_preference} onChange={(event) => setValue('hotel_preference', event.target.value)}><option value="">Choose accommodation</option><option>Budget</option><option>Mid-range</option><option>Luxury</option><option>Boutique</option><option>Hostel</option></select></label>
        <label>Food preference<select value={form.food_preference} onChange={(event) => setValue('food_preference', event.target.value)}><option value="">Choose a food style</option><option>Local</option><option>Vegetarian</option><option>Street food</option><option>Fine dining</option><option>Anything</option></select></label>
      </div>
      <fieldset><legend>Interests</legend><div className="preference-pills">{INTERESTS.map((interest) => <label className={`preference-pill ${form.interests.includes(interest) ? 'is-selected' : ''}`} key={interest}><input type="checkbox" checked={form.interests.includes(interest)} onChange={() => toggleInterest(interest)} />{interest}</label>)}</div></fieldset>
      <label>Preferred destinations<input value={form.preferred_destinations.join(', ')} onChange={(event) => setValue('preferred_destinations', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} placeholder="Goa, Kyoto, Rajasthan" /><small>Separate destinations with commas.</small></label>
      {error && <p className="form-error" role="alert">{error}</p>}{message && <p className="form-success" role="status">{message}</p>}
      <div className="preferences-actions"><Link className="button button-quiet" to="/profile">Back to profile</Link><button className="button button-primary" disabled={saving}>{saving ? 'Saving...' : 'Save preferences'}</button></div>
    </form>}
  </section>
}