import DayCard from './DayCard'
import CriticScore from './CriticScore'
import './PlanCard.css'

export default function PlanCard({ plan }) {
  const { itinerary = [], budget, critic_review, weather, preferences } = plan

  const conditionEmoji = (c = '') => {
    const l = c.toLowerCase()
    if (l.includes('rain')) return '🌧️'
    if (l.includes('cloud')) return '⛅'
    if (l.includes('sun') || l.includes('clear')) return '☀️'
    if (l.includes('storm')) return '⛈️'
    return '🌤️'
  }

  return (
    <div className="plan-card">
      {/* Header */}
      <div className="plan-header">
        <div className="plan-header-left">
          <h2 className="plan-title gradient-text">
            {preferences?.destination ?? 'Your Trip'} Itinerary
          </h2>
          <div className="plan-meta-chips">
            {preferences?.duration && (
              <span className="meta-chip">📅 {preferences.duration} days</span>
            )}
            {weather?.conditions && (
              <span className="meta-chip">
                {conditionEmoji(weather.conditions)} {weather.conditions}
              </span>
            )}
            {weather?.temperature_range && (
              <span className="meta-chip">🌡️ {weather.temperature_range}</span>
            )}
            {preferences?.travel_style && (
              <span className="meta-chip capitalize">🎒 {preferences.travel_style}</span>
            )}
          </div>
        </div>

        {budget && (
          <div className="plan-budget-pill">
            <span className="budget-pill-label">Total Cost</span>
            <span className="budget-pill-value">
              ₹{budget.total_estimated?.toLocaleString()}
            </span>
            <span className={`budget-status ${budget.is_within_budget ? 'within' : 'over'}`}>
              {budget.is_within_budget ? '✓ Within budget' : '⚠ Over budget'}
            </span>
          </div>
        )}
      </div>

      {/* Day cards */}
      <div className="plan-days">
        {itinerary.length === 0 ? (
          <div className="empty-itinerary">
            <span className="empty-icon">🗺️</span>
            <p className="empty-title">Itinerary generation failed</p>
            <p className="empty-sub">
              {critic_review?.warnings?.[0] ?? 'The AI could not build an itinerary for this query. Try rephrasing or reducing the number of days.'}
            </p>
          </div>
        ) : (
          itinerary.map((day, i) => (
            <DayCard key={day.day_number} day={day} index={i} />
          ))
        )}
      </div>

      {/* Critic Review */}
      {critic_review && (
        <CriticScore review={critic_review} />
      )}
    </div>
  )
}
