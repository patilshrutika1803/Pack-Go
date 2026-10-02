import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

async function renderPlan(plan) {
  const server = await createServer({
    configFile: fileURLToPath(new URL('../vite.config.js', import.meta.url)),
    root: fileURLToPath(new URL('..', import.meta.url)),
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true },
    appType: 'custom',
  })

  try {
    const [{ default: PlanCard }, { MemoryRouter }] = await Promise.all([
      server.ssrLoadModule('/src/components/PlanCard.jsx'),
      import('react-router-dom'),
    ])
    return renderToStaticMarkup(createElement(MemoryRouter, null, createElement(PlanCard, { plan })))
  } finally {
    await server.close()
  }
}

test('saved trip map panel shows itinerary stops and opens existing utilities', async () => {
  const markup = await renderPlan({
    trip_id: 'trip-7',
    preferences: { destination: 'Goa' },
    itinerary: [{
      day_number: 1,
      theme: 'Coast',
      attractions: [{ place: { name: 'Fort Aguada' }, timing: 'Morning' }],
    }],
  })

  assert.match(markup, /Saved itinerary stops/)
  assert.match(markup, /Fort Aguada/)
  assert.match(markup, /href="\/trips\/trip-7\?tab=utilities"[^>]*>Open Map/)
  assert.match(markup, /openstreetmap\.org\/search\?query=Fort%20Aguada%2C%20Goa/)
})

test('map panel gives an explicit empty state when no attraction names are saved', async () => {
  const markup = await renderPlan({ preferences: { destination: 'Goa' }, itinerary: [] })

  assert.match(markup, /No attraction locations are saved in this itinerary yet\./)
  assert.doesNotMatch(markup, />Open Map</)
})