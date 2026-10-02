import assert from 'node:assert/strict'
import test from 'node:test'
import { getItinerarySummary, getMessageSenderLabel } from '../src/components/group/groupDisplay.js'

test('itinerary summary counts saved days and activities', () => {
  const summary = getItinerarySummary({
    itinerary: [
      { day_number: 1, activities: ['Walk', 'Museum'] },
      { day_number: 2, activities: ['Market'] },
    ],
  })

  assert.equal(summary.dayCount, 2)
  assert.equal(summary.activityCount, 3)
})

test('itinerary summary handles an empty or malformed itinerary', () => {
  assert.deepEqual(getItinerarySummary({ itinerary: [] }), {
    days: [], dayCount: 0, activityCount: 0,
  })
  assert.equal(getItinerarySummary({ itinerary: [{ activities: null }] }).activityCount, 0)
})

test('chat uses a human-readable sender label and hides missing-user UUIDs', () => {
  assert.equal(getMessageSenderLabel({ sender_name: '  Alex  ', sender_user_id: 'raw-id' }), 'Alex')
  assert.equal(getMessageSenderLabel({ sender_name: null, sender_user_id: 'raw-id' }), 'Former member')
})