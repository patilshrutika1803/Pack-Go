import assert from 'node:assert/strict'
import test from 'node:test'

test('retries an expired authenticated request after rotating its refresh token', async () => {
  const storage = new Map([
    ['pack-go-token', 'expired-access'],
    ['pack-go-refresh-token', 'valid-refresh'],
  ])
  const calls = []
  const dispatched = []
  const previous = { fetch: globalThis.fetch, localStorage: globalThis.localStorage, window: globalThis.window }
  globalThis.localStorage = {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  }
  globalThis.window = {
    dispatchEvent: event => dispatched.push(event.type),
  }
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    if (url === '/api/v1/notifications' && calls.length === 1) {
      return new Response(JSON.stringify({ error: 'Invalid access token.' }), { status: 401 })
    }
    if (url === '/api/v1/auth/refresh') {
      return new Response(JSON.stringify({
        access_token: 'new-access',
        refresh_token: 'new-refresh',
        user: { id: 'user-1', name: 'Traveler' },
      }), { status: 200 })
    }
    return new Response(JSON.stringify({ notifications: [] }), { status: 200 })
  }

  try {
    const { notificationsApi } = await import('../src/api/client.js')
    const result = await notificationsApi.list()

    assert.deepEqual(result, { notifications: [] })
    assert.equal(calls.length, 3)
    assert.equal(calls[1].url, '/api/v1/auth/refresh')
    assert.equal(calls[2].options.headers.Authorization, 'Bearer new-access')
    assert.equal(storage.get('pack-go-refresh-token'), 'new-refresh')
    assert.equal(dispatched.includes('pack-go-session-expired'), false)
  } finally {
    globalThis.fetch = previous.fetch
    globalThis.localStorage = previous.localStorage
    globalThis.window = previous.window
  }
})