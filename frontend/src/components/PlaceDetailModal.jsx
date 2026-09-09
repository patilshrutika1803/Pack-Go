import { useEffect, useRef } from 'react'
import './PlaceDetailModal.css'

function hasValue(value, placeholders = []) {
  return value !== undefined && value !== null && value !== '' && !placeholders.includes(value)
}

export default function PlaceDetailModal({ place, timing, onClose }) {
  const closeButtonRef = useRef(null)

  useEffect(() => {
    closeButtonRef.current?.focus()
  }, [])

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget) onClose()
  }

  const description = hasValue(place?.description, ['No description provided.'])
  const category = hasValue(place?.category, ['attraction'])
  const entryFee = hasValue(place?.entry_fee, ['Unknown'])
  const duration = hasValue(place?.recommended_duration_hours)
  const bestTime = hasValue(place?.best_time_to_visit, ['Anytime'])

  return (
    <div
      className="place-modal-backdrop"
      role="presentation"
      onMouseDown={handleBackdropClick}
    >
      <section
        className="place-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="place-modal-title"
      >
        <div className="place-modal-photo" aria-hidden="true"><span>PACK &amp; GO / PLACE GUIDE</span></div><div className="place-modal-header">
          <div>
            <p className="place-modal-eyebrow">Place details</p>
            <h2 id="place-modal-title">{place?.name}</h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="place-modal-close"
            onClick={onClose}
            aria-label="Close place details"
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>

        {description && <p className="place-modal-description">{place.description}</p>}

        <div className="place-modal-details">
          {timing && <Detail label="Visit timing" value={timing} />}
          {category && <Detail label="Category" value={place.category} />}
          {entryFee && <Detail label="Entry fee" value={place.entry_fee} />}
          {duration && <Detail label="Recommended time" value={`${place.recommended_duration_hours} hours`} />}
          {bestTime && <Detail label="Best time to visit" value={place.best_time_to_visit} />}
        </div>
        <div className="place-modal-actions"><button className="outline-button" type="button">Open map</button><button className="button button-primary" type="button">Add to itinerary</button></div>
      </section>
    </div>
  )
}

function Detail({ label, value }) {
  return (
    <div className="place-detail">
      <span className="place-detail-label">{label}</span>
      <span className="place-detail-value">{value}</span>
    </div>
  )
}