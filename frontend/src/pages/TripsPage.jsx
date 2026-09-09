import { Link } from 'react-router-dom'

const TRIPS = [
  { name: 'Goa', detail: '3 days · 2 travelers', tags: 'Beach · Food · Nature', cost: '₹9,000 estimated', image: 'photo-1512343879784-a960bf40e7f2', color: 'pink' },
  { name: 'Rajasthan', detail: '5 days · 2 travelers', tags: 'Culture · History · Food', cost: '₹18,500 estimated', image: 'photo-1477587458883-47145ed94245', color: 'yellow' },
]

export default function TripsPage() {
  return <section className="trips-page page-container"><div className="page-title-row"><div><p className="eyebrow">Your travel shelf</p><h1>My trips</h1><p className="page-lede">The places you are dreaming about, all in one place.</p></div><Link className="button button-primary" to="/plan">+ Plan a new trip</Link></div><div className="trip-tabs"><button className="selected">Upcoming <span>2</span></button><button>Past</button><button>Saved</button></div><div className="trip-grid">{TRIPS.map(trip => <article className="saved-trip-card" key={trip.name}><div className="saved-trip-image" style={{ backgroundImage: `url(https://images.unsplash.com/${trip.image}?auto=format&fit=crop&w=1000&q=85)` }}><span className={`trip-label ${trip.color}`}>Upcoming</span><button aria-label={`Save ${trip.name}`}>♡</button></div><div className="saved-trip-copy"><p className="eyebrow">{trip.detail}</p><h2>{trip.name}</h2><p>{trip.tags}</p><div className="saved-trip-footer"><strong>{trip.cost}</strong><Link to="/plan">Open trip ↗</Link></div></div></article>)}</div></section>
}