import { Link } from 'react-router-dom'

const features = [
  ['✦', 'AI trip planning', 'Turn a loose idea into a trip worth taking.', 'var(--pink)'],
  ['↗', 'Smart itinerary', 'A day-by-day plan that leaves room for wonder.', 'var(--primary)'],
  ['◌', 'Budget planning', 'Know what the journey costs before you go.', 'var(--yellow)'],
  ['☼', 'Live weather', 'Make better calls with what is happening there now.', 'var(--teal)'],
  ['⌁', 'Packing help', 'The right things in your bag, none of the noise.', 'var(--pink)'],
  ['∞', 'Travel assistant', 'A calm co-pilot for every question along the way.', 'var(--primary)'],
]

export default function LandingPage() {
  return <>
    <section className="landing-hero page-container">
      <div className="hero-copy"><p className="eyebrow">AI-powered travel planning</p><h1>Plan less.<br /><em>Travel more.</em></h1><p className="hero-lede">From first spark to final boarding pass, PACK &amp; GO helps you make more of the places you have been dreaming about.</p><div className="hero-actions"><Link className="button button-primary" to="/plan">Plan my trip <span>↗</span></Link><Link className="button button-quiet" to="/explore">Explore destinations</Link></div><div className="hero-note"><span className="note-dot" /> Built for curious people with somewhere to be</div></div>
      <div className="hero-art"><div className="hero-photo" /><div className="floating-card card-location"><span>◎</span><strong>Somewhere<br />beautiful</strong></div><div className="floating-card card-stamp">GO<br /><small>ANYWHERE</small></div><div className="sun-shape" /></div>
    </section>
    <section className="section page-container"><div className="section-heading"><p className="eyebrow">The good stuff</p><h2>Everything for<br /><em>your journey.</em></h2></div><div className="feature-grid">{features.map(([icon, title, text, color]) => <article className="feature-card" key={title} style={{ '--card-color': color }}><span className="feature-icon">{icon}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
    <section className="people-band page-container"><div><p className="eyebrow">Coming together</p><h2>Plan with<br /><em>your people.</em></h2><p>Good trips get better when everyone has a say. Shared planning is on its way.</p></div><div className="people-art"><span>✦</span><span>✺</span><span>✹</span><div className="people-ticket">NEXT STOP<br /><b>EVERYWHERE</b></div></div></section>
    <section className="all-in-one page-container"><div className="section-heading"><p className="eyebrow">One happy place</p><h2>Your trip,<br /><em>all in one place.</em></h2></div><div className="trip-preview"><div className="preview-map"><div className="map-line" /><span className="map-pin pin-one">1</span><span className="map-pin pin-two">2</span><span className="map-pin pin-three">3</span></div><div className="preview-copy"><p className="eyebrow">Your next adventure</p><h3>Lisbon, Portugal</h3><p>Itinerary, budget, places to stay, and the little details that make a trip yours.</p><div className="preview-pills"><span>7 days</span><span>€1,240</span><span>8 places</span></div></div></div></section>
    <section className="final-cta page-container"><p className="eyebrow">Ready when you are</p><h2>There is a whole<br /><em>world to go see.</em></h2><Link className="button button-primary" to="/plan">Start planning <span>↗</span></Link></section>
  </>
}
