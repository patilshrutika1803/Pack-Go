import { Link } from 'react-router-dom'

const DESTINATIONS = [
  { name: 'Goa', tag: 'Beach · Food · Slow days', image: 'photo-1512343879784-a960bf40e7f2', color: 'pink' },
  { name: 'Rajasthan', tag: 'Culture · Colour · History', image: 'photo-1477587458883-47145ed94245', color: 'yellow' },
  { name: 'Himachal', tag: 'Mountains · Trails · Fresh air', image: 'photo-1501785888041-af3ef285b470', color: 'teal' },
  { name: 'Coorg', tag: 'Coffee · Nature · Quiet', image: 'photo-1464822759023-fed622ff2c3b', color: 'blue' },
]

export default function ExplorePage() {
  return <section className="explore-page page-container"><div className="explore-hero"><div><p className="eyebrow">Explore the good stuff</p><h1>Where will you <em>go next?</em></h1><p>Find a place that fits the mood, then let PACK &amp; GO shape the details.</p></div><div className="explore-search"><span>⌕</span><input placeholder="Search a destination" aria-label="Search a destination" /></div></div><div className="collection-row"><span>Browse by feeling</span>{['Weekend escapes', 'Budget friendly', 'Beach', 'Mountains', 'Culture', 'Adventure'].map((item, index) => <button className={`collection-tab tab-${index}`} key={item}>{item}</button>)}</div><div className="destination-grid">{DESTINATIONS.map(destination => <Link className="destination-card" to={`/plan?destination=${destination.name}`} key={destination.name}><div className="destination-image" style={{ backgroundImage: `url(https://images.unsplash.com/${destination.image}?auto=format&fit=crop&w=900&q=85)` }} /><div className="destination-copy"><span className={`destination-dot ${destination.color}`} /><div><h2>{destination.name}</h2><p>{destination.tag}</p></div><span className="destination-arrow">↗</span></div></Link>)}</div><div className="explore-footer-callout"><div><p className="eyebrow">Make it yours</p><h2>A trip that starts with a feeling.</h2></div><Link className="button button-primary" to="/plan">Start planning <span>↗</span></Link></div></section>
}