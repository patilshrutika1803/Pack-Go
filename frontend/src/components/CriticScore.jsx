import { useEffect, useRef } from 'react'
import './CriticScore.css'

const SCORE_COLOR = (s) => {
  if (s >= 8) return '#00d4aa'
  if (s >= 6) return '#f5a623'
  return '#ff5e7a'
}

export default function CriticScore({ review }) {
  const {
    overall_score = 0,
    highlights = [],
    warnings = [],
    logical_flow_score,
    budget_alignment_score,
    weather_suitability_score,
    preference_match_score,
  } = review

  const circleRef = useRef(null)
  const R = 44
  const CIRC = 2 * Math.PI * R
  const pct  = overall_score / 10
  const color = SCORE_COLOR(overall_score)

  useEffect(() => {
    if (!circleRef.current) return
    circleRef.current.style.strokeDashoffset = CIRC * (1 - pct)
  }, [overall_score])

  const subScores = [
    { label: 'Logical Flow',   val: logical_flow_score },
    { label: 'Budget Match',   val: budget_alignment_score },
    { label: 'Weather Fit',    val: weather_suitability_score },
    { label: 'Pref. Match',    val: preference_match_score },
  ].filter(s => s.val != null)

  return (
    <div className="critic-card glass">
      <div className="critic-header">
        {/* Score ring */}
        <div className="score-ring-wrap">
          <svg width="110" height="110" viewBox="0 0 110 110">
            <circle cx="55" cy="55" r={R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8"/>
            <circle
              ref={circleRef}
              cx="55" cy="55" r={R}
              fill="none"
              stroke={color}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={CIRC}
              strokeDashoffset={CIRC}
              style={{
                transform: 'rotate(-90deg)',
                transformOrigin: '55px 55px',
                transition: 'stroke-dashoffset 1.4s cubic-bezier(.4,0,.2,1)',
                filter: `drop-shadow(0 0 6px ${color}88)`,
              }}
            />
          </svg>
          <div className="score-label">
            <span className="score-val" style={{ color }}>{overall_score.toFixed(1)}</span>
            <span className="score-denom">/10</span>
          </div>
        </div>

        <div className="critic-right">
          <p className="critic-title">📊 Critic Review</p>

          {/* Sub-scores */}
          {subScores.length > 0 && (
            <div className="sub-scores">
              {subScores.map(s => (
                <div key={s.label} className="sub-score-row">
                  <span className="sub-label">{s.label}</span>
                  <div className="sub-bar-track">
                    <div
                      className="sub-bar-fill"
                      style={{ width: `${(s.val / 10) * 100}%`, background: SCORE_COLOR(s.val) }}
                    />
                  </div>
                  <span className="sub-val">{s.val?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Highlights */}
      {highlights.length > 0 && (
        <div className="critic-section">
          <p className="critic-section-title">✅ Highlights</p>
          <ul className="critic-list">
            {highlights.map((h, i) => (
              <li key={i} className="highlight-item">{h}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="critic-section">
          <p className="critic-section-title">⚠️ Warnings</p>
          <ul className="critic-list">
            {warnings.map((w, i) => (
              <li key={i} className="warning-item">{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
