import assert from 'node:assert/strict'
import test from 'node:test'

test('API client uses the configured backend origin and no legacy token storage', async () => {
  const previous = {
    fetch: globalThis.fetch,
    supabaseUrl: process.env.VITE_SUPABASE_URL,
    supabaseKey: process.env.VITE_SUPABASE_ANON_KEY,
    apiBaseUrl: process.env.VITE_API_BASE_URL,
  }
  process.env.VITE_SUPABASE_URL = 'https://supabase.example.test'
  process.env.VITE_SUPABASE_ANON_KEY = 'public-anon-test-key'
  process.env.VITE_API_BASE_URL = 'https://api.example.test/'
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    if (url === 'https://supabase.example.test/auth/v1/user') {
      return new Response(JSON.stringify({
        id: 'supabase-user',
        aud: 'authenticated',
        role: 'authenticated',
        email: 'traveler@example.test',
        app_metadata: { provider: 'email', providers: ['email'] },
        user_metadata: {},
        created_at: new Date().toISOString(),
        identities: [],
      }), { status: 200 })
    }
    return new Response(JSON.stringify({ notifications: [] }), { status: 200 })
  }

  try {
    const { notificationsApi, apiUrl } = await import('../src/api/client.js')
    const { getSupabaseClient } = await import('../src/auth/supabase.js')
    const accessToken = [
      Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url'),
      Buffer.from(JSON.stringify({ sub: 'supabase-user', exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url'),
      'test-signature',
    ].join('.')
    const { error } = await getSupabaseClient().auth.setSession({
      access_token: accessToken,
      refresh_token: 'test-refresh-token',
    })
    assert.equal(error, null)
    assert.equal(apiUrl('/plan/stream'), 'https://api.example.test/plan/stream')
    assert.deepEqual(await notificationsApi.list(), { notifications: [] })
    const backendCall = calls.find((call) => call.url === 'https://api.example.test/api/v1/notifications')
    assert.ok(backendCall)
    assert.equal(backendCall.options.headers.Authorization, `Bearer ${accessToken}`)
  } finally {
    globalThis.fetch = previous.fetch
    if (previous.supabaseUrl === undefined) delete process.env.VITE_SUPABASE_URL
    else process.env.VITE_SUPABASE_URL = previous.supabaseUrl
    if (previous.supabaseKey === undefined) delete process.env.VITE_SUPABASE_ANON_KEY
    else process.env.VITE_SUPABASE_ANON_KEY = previous.supabaseKey
    if (previous.apiBaseUrl === undefined) delete process.env.VITE_API_BASE_URL
    else process.env.VITE_API_BASE_URL = previous.apiBaseUrl
  }
})
