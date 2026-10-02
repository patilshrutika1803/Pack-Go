const API_BASE = '/api/v1'
const LEGACY_PLAN_ERROR = 'Unable to generate the travel plan at this time. Please try again.'
const PREFERENCE_ERROR = 'Unable to save your preferences. Please try again.'
const PREFERENCE_VALIDATION_ERROR = 'Some preference values are invalid. Please check your selections.'
const PREFERENCE_FIELDS = ['travel_style', 'interests', 'things_to_avoid', 'budget_preference', 'hotel_preference', 'food_preference', 'preferred_destinations', 'preferred_budget_min', 'preferred_budget_max', 'preferred_currency', 'preferred_trip_duration', 'is_domestic']
const TOKEN_KEY = 'pack-go-token'
const REFRESH_KEY = 'pack-go-refresh-token'
let refreshRequest

function refreshAccessToken() {
  if (!refreshRequest) {
    refreshRequest = (async () => {
      const refreshToken = localStorage.getItem(REFRESH_KEY)
      if (!refreshToken) throw new Error('No refresh token is available.')
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || !result.access_token || !result.refresh_token) {
        throw new Error('Unable to refresh the session.')
      }
      localStorage.setItem(TOKEN_KEY, result.access_token)
      localStorage.setItem(REFRESH_KEY, result.refresh_token)
      localStorage.setItem('pack-go-user', JSON.stringify(result.user))
      window.dispatchEvent(Object.assign(new Event('pack-go-session-refreshed'), { detail: result }))
      return result.access_token
    })().finally(() => { refreshRequest = null })
  }
  return refreshRequest
}

function authErrorMessage(path, detail) {
  if (Array.isArray(detail)) {
    const first = detail[0] || {}
    return `${first.loc?.at(-1) || 'request'}: ${first.msg || 'Invalid authentication request.'}`
  }
  if (detail && detail !== LEGACY_PLAN_ERROR) return detail
  if (path === '/auth/register') return 'Unable to create your account right now. Please try again.'
  if (path === '/auth/login') return "Email or password doesn't look right. Please try again."
  return 'Unable to complete authentication right now. Please try again.'
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const send = (token) => fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token && !options.headers?.Authorization ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
      ...(token && options.headers?.Authorization ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  let response = await send(localStorage.getItem(TOKEN_KEY))
  if (response.status === 401 && !path.startsWith('/auth/')) {
    try {
      response = await send(await refreshAccessToken())
    } catch {
      window.dispatchEvent(new Event('pack-go-session-expired'))
    }
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('pack-go-session-expired'))
    const detail = body.detail || body.error
    const message = path.startsWith('/auth/')
      ? authErrorMessage(path, detail)
      : path.startsWith('/users/me/preferences') && response.status === 422
        ? PREFERENCE_VALIDATION_ERROR
      : path.startsWith('/users/me/preferences') && (!detail || detail === LEGACY_PLAN_ERROR)
        ? PREFERENCE_ERROR
        : detail || 'Something went wrong. Please try again.'
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return body
}

export const authApi = {
  register: (payload) => request('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) => request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  refresh: (refreshToken) => request('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) }),
  logout: (refreshToken) => request('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) }),
  me: (token) => request('/users/me', { headers: { Authorization: `Bearer ${token}` } }),
  verifyEmail: (token) => request('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),
  forgotPassword: (email) => request('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (token, password) => request('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password }) }),
}

export const tripsApi = {
  list: () => request('/trips'),
  get: (id) => request(`/trips/${id}`),
  create: (payload) => request('/trips', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/trips/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  remove: (id) => request(`/trips/${id}`, { method: 'DELETE' }),
  regenerateDay: (id, dayNumber) => request(`/trips/${id}/days/${dayNumber}/regenerate`, { method: 'PATCH' }),
  packing: (id) => request(`/trips/${id}/utilities/packing`),
  map: (id) => request(`/trips/${id}/utilities/map`),
  routeLocations: (id) => request(`/trips/${id}/route/locations`),
  optimizeRoute: (id, payload) => request(`/trips/${id}/route/optimize`, { method: 'POST', body: JSON.stringify(payload) }),
  optimizeItineraryCsp: (id) => request(`/trips/${id}/itinerary/csp-optimize`, { method: 'POST', body: JSON.stringify({}) }),
  optimizeItineraryGa: (id, payload = {}) => request(`/trips/${id}/itinerary/ga-optimize`, { method: 'POST', body: JSON.stringify(payload) }),
}

export const placesApi = {
  search: (location, category) => request(`/utilities/places?location=${encodeURIComponent(location)}&category=${encodeURIComponent(category)}`),
}

export const weatherApi = {
  current: (location) => request(`/utilities/weather?location=${encodeURIComponent(location)}`),
}

export const currencyApi = {
  convert: (amount, fromCurrency, toCurrency) => request(`/utilities/currency?amount=${encodeURIComponent(amount)}&from_currency=${encodeURIComponent(fromCurrency)}&to_currency=${encodeURIComponent(toCurrency)}`),
}

export const expensesApi = {
  list: (tripId) => request(`/trips/${tripId}/expenses`),
  summary: (tripId) => request(`/trips/${tripId}/expenses/summary`),
  create: (tripId, payload) => request(`/trips/${tripId}/expenses`, { method: 'POST', body: JSON.stringify(payload) }),
  update: (expenseId, payload) => request(`/expenses/${expenseId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  remove: (expenseId) => request(`/expenses/${expenseId}`, { method: 'DELETE' }),
}

export const journalApi = {
  list: (tripId) => request(`/trips/${tripId}/journal`),
  statistics: (tripId) => request(`/trips/${tripId}/journal/statistics`),
  create: (tripId, payload) => request(`/trips/${tripId}/journal`, { method: 'POST', body: JSON.stringify(payload) }),
  update: (entryId, payload) => request(`/journal-entries/${entryId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  remove: (entryId) => request(`/journal-entries/${entryId}`, { method: 'DELETE' }),
}

export const groupTripsApi = {
  workspace: (id) => request(`/trips/${id}/workspace`),
  convert: (id) => request(`/trips/${id}/group`, { method: 'POST', body: JSON.stringify({}) }),
}

export const membersApi = {
  list: (id) => request(`/trips/${id}/members`),
  updateRole: (tripId, userId, role) => request(`/trips/${tripId}/members/${userId}`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  remove: (tripId, userId) => request(`/trips/${tripId}/members/${userId}`, { method: 'DELETE' }),
  leave: (tripId) => request(`/trips/${tripId}/leave`, { method: 'POST', body: JSON.stringify({}) }),
  transfer: (tripId, target_user_id) => request(`/trips/${tripId}/ownership`, { method: 'POST', body: JSON.stringify({ target_user_id }) }),
}

export const invitationsApi = {
  list: (id) => request(`/trips/${id}/invitations`),
  create: (id, payload) => request(`/trips/${id}/invitations`, { method: 'POST', body: JSON.stringify(payload) }),
  preview: (token) => request(`/invitations/${token}`),
  accept: (token) => request(`/invitations/${token}/accept`, { method: 'POST', body: JSON.stringify({}) }),
  revoke: (id) => request(`/trip-invitations/${id}/revoke`, { method: 'POST', body: JSON.stringify({}) }),
}

export const proposalsApi = {
  list: (id) => request(`/trips/${id}/proposals`),
  create: (id, payload) => request(`/trips/${id}/proposals`, { method: 'POST', body: JSON.stringify(payload) }),
  vote: (id, choice_key) => request(`/proposals/${id}/vote`, { method: 'PUT', body: JSON.stringify({ choice_key }) }),
  removeVote: (id) => request(`/proposals/${id}/vote`, { method: 'DELETE' }),
  update: (id, payload) => request(`/proposals/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  close: (id) => request(`/proposals/${id}/close`, { method: 'POST', body: JSON.stringify({}) }),
  results: (id) => request(`/proposals/${id}/results`),
  finalize: (id) => request(`/proposals/${id}/finalize`, { method: 'POST', body: JSON.stringify({}) }),
  decision: (id) => request(`/proposals/${id}/decision`),
}

export const decisionsApi = {
  list: (id) => request(`/trips/${id}/decisions`),
  get: (id) => request(`/proposals/${id}/decision`),
  apply: (id) => request(`/decisions/${id}/apply`, { method: 'POST', body: JSON.stringify({}) }),
  replan: (id) => request(`/decisions/${id}/replan`, { method: 'POST', body: JSON.stringify({}) }),
}

export const checklistApi = {
  list: (id, filters = {}) => {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''))
    return request(`/trips/${id}/checklist${query.toString() ? `?${query}` : ''}`)
  },
  create: (id, payload) => request(`/trips/${id}/checklist`, { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/checklist-items/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  complete: (id) => request(`/checklist-items/${id}/complete`, { method: 'POST', body: JSON.stringify({}) }),
  reopen: (id) => request(`/checklist-items/${id}/reopen`, { method: 'POST', body: JSON.stringify({}) }),
  remove: (id) => request(`/checklist-items/${id}`, { method: 'DELETE' }),
}

export const messagesApi = {
  list: (id, cursor) => request(`/trips/${id}/messages${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`),
  create: (id, body) => request(`/trips/${id}/messages`, { method: 'POST', body: JSON.stringify({ body }) }),
  update: (id, body) => request(`/messages/${id}`, { method: 'PATCH', body: JSON.stringify({ body }) }),
  remove: (id) => request(`/messages/${id}`, { method: 'DELETE' }),
}

export const notificationsApi = {
  list: () => request('/notifications'),
  unreadCount: () => request('/notifications/unread-count'),
  read: (id) => request(`/notifications/${id}/read`, { method: 'PATCH', body: JSON.stringify({}) }),
  readAll: () => request('/notifications/read-all', { method: 'POST', body: JSON.stringify({}) }),
}

export const preferencesApi = {
  get: () => request('/users/me/preferences'),
  update: (payload) => request('/users/me/preferences', {
    method: 'PATCH',
    body: JSON.stringify(Object.fromEntries(PREFERENCE_FIELDS.filter((field) => field in payload).map((field) => [field, payload[field]]))),
  }),
}

export const knowledgeApi = {
  list: (filters = {}) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value))
    return request(`/admin/knowledge/documents${params.toString() ? `?${params}` : ''}`)
  },
  userList: (filters = {}) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value))
    return request(`/knowledge${params.toString() ? `?${params}` : ''}`)
  },
  ask: (payload) => request('/knowledge/ask', { method: 'POST', body: JSON.stringify(payload) }),
  upload: (formData) => request('/admin/knowledge/documents', { method: 'POST', body: formData }),
  reindex: (id) => request(`/admin/knowledge/documents/${id}/reindex`, { method: 'POST' }),
  remove: (id) => request(`/admin/knowledge/documents/${id}`, { method: 'DELETE' }),
}

export const adminApi = {
  overview: () => request('/admin/overview'),
}
