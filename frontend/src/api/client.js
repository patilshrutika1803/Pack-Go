import { getSupabaseClient } from '../auth/supabase.js'

const processEnvironment = typeof process === 'undefined' ? {} : process.env
const API_BASE_URL = (((import.meta.env || {}).VITE_API_BASE_URL || processEnvironment.VITE_API_BASE_URL) || '').replace(/\/+$/, '')
const PREFERENCE_ERROR = 'Unable to save your preferences. Please try again.'
const PREFERENCE_VALIDATION_ERROR = 'Some preference values are invalid. Please check your selections.'
const PREFERENCE_FIELDS = ['travel_style', 'interests', 'things_to_avoid', 'budget_preference', 'hotel_preference', 'food_preference', 'preferred_destinations', 'preferred_budget_min', 'preferred_budget_max', 'preferred_currency', 'preferred_trip_duration', 'is_domestic']

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData
  const send = (token) => fetch(apiUrl(`/api/v1${path}`), {
    ...options,
    headers: {
      ...(!isFormData && options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })
  const supabase = getSupabaseClient()
  const { data, error } = await supabase.auth.getSession()
  if (error) throw error
  let response = await send(data.session?.access_token)
  if (response.status === 401 && data.session) {
    const { data: refreshed, error: refreshError } = await supabase.auth.refreshSession()
    if (refreshError) {
      const { error: signOutError } = await supabase.auth.signOut()
      if (signOutError) throw signOutError
    } else if (refreshed.session?.access_token) {
      response = await send(refreshed.session.access_token)
    }
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = body.detail || body.error
    const message = path.startsWith('/users/me/preferences') && response.status === 422
      ? PREFERENCE_VALIDATION_ERROR
      : path.startsWith('/users/me/preferences') && !detail
        ? PREFERENCE_ERROR
        : detail || 'Something went wrong. Please try again.'
    const apiError = new Error(message)
    apiError.status = response.status
    throw apiError
  }
  return body
}

export const authApi = {
  me: () => request('/users/me'),
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
