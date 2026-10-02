import DayCard from './DayCard'
import CriticScore from './CriticScore'
import { formatCurrency, resolveCurrency } from '../utils/currency'
import { Link } from 'react-router-dom'
import './PlanCard.css'

export default function PlanCard({ plan, onRegenerate }) {
  const { itinerary = [], budget, critic_review, weather, preferences } = plan
  const currency = resolveCurrency(plan)
  const mapStops = itinerary.flatMap(day => (Array.isArray(day.attractions) ? day.attractions : [])
    .map(attraction => ({ dayNumber: day.day_number, name: attraction.place?.name }))
    .filter(stop => typeof stop.name === 'string' && stop.name.trim()))
  const destination = preferences?.destination
  const mapSearchUrl = name => `https://www.openstreetmap.org/search?query=${encodeURIComponent([name, destination].filter(Boolean).join(', '))}`

  return <div className="plan-card">
    <div className="plan-header">
      <div className="plan-header-left">
        <p className="eyebrow">Your trip is ready</p>
        <h2 className="plan-title">{destination ?? 'Your Trip'}</h2>
        <p className="plan-subtitle">{preferences?.duration || itinerary.length} days · {preferences?.travelers || preferences?.number_of_travelers || 2} travelers · {preferences?.travel_style || 'curated for you'}</p>
        <div className="plan-meta-chips">
          <span className="meta-chip"><span className="meta-chip-mark">☼</span> {weather?.conditions || 'Good conditions'}</span>
          {weather?.temperature_range && <span className="meta-chip"><span className="meta-chip-mark">°</span> {weather.temperature_range}</span>}
        </div>
      </div>
      {budget && <div className="plan-budget-pill">
        <span className="budget-pill-label">Estimated total</span>
        <span className="budget-pill-value">{formatCurrency(budget.total_estimated, currency)}</span>
        <span className={`budget-status ${budget.is_within_budget ? 'within' : 'over'}`}>{budget.is_within_budget ? 'Within your budget' : 'Over your budget'}</span>
      </div>}
    </div>
    {budget && <BudgetSummary budget={budget} preferences={preferences} currency={currency} />}
    <div className="plan-workspace">
      <div className="plan-days">
        <div className="section-heading-inline">
          <div><p className="eyebrow">The rhythm of your trip</p><h3>Itinerary</h3></div>
          {plan.trip_id && <Link className="outline-button" to={`/trips/${plan.trip_id}`}>Open saved trip</Link>}
        </div>
        {itinerary.length === 0
          ? <div className="empty-itinerary"><span className="empty-icon">Map</span><p className="empty-title">Itinerary generation failed</p><p className="empty-sub">{critic_review?.warnings?.[0] ?? 'The AI could not build an itinerary for this query. Try rephrasing or reducing the number of days.'}</p></div>
          : itinerary.map((day, index) => <DayCard key={day.day_number} day={day} index={index} currency={currency} onRegenerate={onRegenerate} />)}
      </div>
      <div className="map-panel">
        <div className="map-panel-top">
          <div><p className="eyebrow">Route at a glance</p><h3>Saved itinerary stops</h3></div>
          {plan.trip_id && <Link className="outline-button" to={`/trips/${plan.trip_id}?tab=utilities`}>Open Map</Link>}
        </div>
        {mapStops.length ? <ol className="map-itinerary-stops">
          {mapStops.map((stop, index) => <li key={`${stop.dayNumber}-${index}`}><span>Day {stop.dayNumber}</span><a href={mapSearchUrl(stop.name)} target="_blank" rel="noreferrer">{stop.name}</a></li>)}
        </ol> : <p className="map-empty-state">No attraction locations are saved in this itinerary yet.</p>}
        <p className="map-note">Place links search OpenStreetMap. Route optimization is available when saved coordinates exist.</p>
      </div>
    </div>
    <details className="ai-transparency"><summary>How PACK &amp; GO built this <span>+</span></summary><div className="ai-steps">{['Supervisor', 'Preference analysis', 'Research', 'Weather', 'Budget', 'Itinerary', 'Review'].map((step, index) => <div key={step}><span>{String(index + 1).padStart(2, '0')}</span>{step}</div>)}</div></details>
    {critic_review && <CriticScore review={critic_review} />}
  </div>
}

function BudgetSummary({ budget, preferences, currency }) {
  const total = Number(budget.total_estimated) || 0
  const limit = Number(preferences?.total_budget) || total
  const categories = (budget.categories || []).map(category => ({ label: category.name, value: category.amount }))
  return <section className="budget-summary"><div><p className="eyebrow">Your trip budget</p><h3>{formatCurrency(total, currency)} <span>of {formatCurrency(limit, currency)}</span></h3><div className="budget-progress"><span style={{ width: `${Math.min(100, (total / limit) * 100)}%` }} /></div><p className="budget-remaining">{budget.is_within_budget ? `✓ ${formatCurrency(Math.max(0, limit - total), currency)} remaining` : 'Review the plan to bring it within budget'}</p></div><div className="budget-breakdown">{categories.map(item => <div key={item.label}><span>{item.label}</span><strong>{formatCurrency(item.value, currency)}</strong></div>)}</div></section>
}
