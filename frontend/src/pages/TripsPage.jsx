import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { tripsApi } from '../api/client'
import { useAuth } from '../auth/useAuth'

export default function TripsPage() {
  const { user } = useAuth()
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => { tripsApi.list().then(setTrips).catch(err => setError(err.message)).finally(() => setLoading(false)) }, [])
  return <section className="trips-page page-container"><div className="page-title-row"><div><p className="eyebrow">Welcome back, {user?.name || 'traveler'}</p><h1>My trips</h1><p className="page-lede">Your saved journeys, ready when you are.</p></div><Link className="button button-primary" to="/plan">+ Plan a new trip</Link></div><div className="trip-tabs"><button className="selected">All trips <span>{trips.length}</span></button><Link className="button button-quiet" to="/profile">Profile</Link></div>{loading && <p className="page-lede">Loading your trips...</p>}{error && <p className="form-error" role="alert">{error}</p>}{!loading && !error && trips.length === 0 && <div className="empty-itinerary"><p className="empty-title">No trips saved yet</p><p className="empty-sub">Start with an idea and your next itinerary will appear here.</p><Link className="button button-primary" to="/plan">Create your first trip</Link></div>}<div className="trip-grid">{trips.map(trip => <article className="saved-trip-card" key={trip.id}><div className="saved-trip-image" style={{ backgroundImage: `url(https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1000&q=85)` }}><span className="trip-label pink">Saved</span></div><div className="saved-trip-copy"><p className="eyebrow">{trip.duration} days · {trip.group_size} travelers</p><h2>{trip.destination}</h2><p>{trip.travel_dates || 'Dates not set'} · {trip.travel_style}</p><div className="saved-trip-footer"><strong>{trip.budget_currency} {trip.total_budget.toLocaleString()}</strong><Link to={`/trips/${trip.id}`}>Open trip ↗</Link></div></div></article>)}</div></section>
}