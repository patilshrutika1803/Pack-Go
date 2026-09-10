import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { tripsApi } from '../api/client'
import PlanCard from '../components/PlanCard'

function tripToPlan(trip) {
  return {
    trip_id: trip.id,
    preferences: {
      destination: trip.destination,
      duration: trip.duration,
      total_budget: trip.total_budget,
      budget_currency: trip.budget_currency,
      group_size: trip.group_size,
      travelers: trip.group_size,
      travel_style: trip.travel_style,
      travel_dates: trip.travel_dates,
      interests: trip.interests,
    },
    itinerary: trip.itinerary,
    weather: trip.weather,
    budget: trip.budget_breakdown,
    critic_review: trip.critic_review,
  }
}

export default function TripDetailPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const [trip, setTrip] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => { tripsApi.get(tripId).then(setTrip).catch(err => setError(err.message)).finally(() => setLoading(false)) }, [tripId])
  const remove = async () => {
    if (!window.confirm('Delete this trip permanently?')) return
    try { await tripsApi.remove(tripId); navigate('/trips', { replace: true, state: { message: 'Trip deleted successfully.' } }) } catch (err) { setError(err.message) }
  }
  const regenerate = async (dayNumber) => {
    setMessage('Regenerating day...'); setError('')
    try {
      const result = await tripsApi.regenerateDay(tripId, dayNumber)
      setTrip(current => ({ ...current, itinerary: current.itinerary.map(day => day.day_number === dayNumber ? result.regenerated_day : day), updated_at: result.updated_at }))
      setMessage(`Day ${dayNumber} regenerated successfully.`)
    } catch (err) { setError(err.message); setMessage('') }
  }
  if (loading) return <section className="page-container placeholder"><p className="eyebrow">Trip detail</p><h1>Loading your itinerary...</h1></section>
  if (error || !trip) return <section className="page-container placeholder"><p className="form-error" role="alert">{error || 'Trip not found.'}</p><Link className="button button-primary" to="/trips">Back to My Trips</Link></section>
  return <section className="page-container trips-page"><div className="page-title-row"><div><Link to="/trips" className="text-button">← My trips</Link><p className="eyebrow">Saved trip</p><h1>{trip.destination}</h1><p className="page-lede">Created {new Date(trip.created_at).toLocaleDateString()}</p></div><button className="button button-quiet" onClick={remove}>Delete trip</button></div>{message && <p className="page-lede" role="status">{message}</p>}<PlanCard plan={tripToPlan(trip)} onRegenerate={regenerate} /></section>
}