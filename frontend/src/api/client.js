const API_BASE = '/api/v1'
const LEGACY_PLAN_ERROR = 'Unable to generate the travel plan at this time. Please try again.'
const PREFERENCE_ERROR = 'Unable to save your preferences. Please try again.'
const PREFERENCE_VALIDATION_ERROR = 'Some preference values are invalid. Please check your selections.'
const PREFERENCE_FIELDS = ['travel_style', 'interests', 'things_to_avoid', 'budget_preference', 'hotel_preference', 'food_preference', 'preferred_destinations', 'preferred_budget_min', 'preferred_budget_max', 'preferred_currency', 'preferred_trip_duration', 'is_domestic']

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
  const token = localStorage.getItem('pack-go-token')
  const authorization = token && !options.headers?.Authorization ? { Authorization: `Bearer ${token}` } : {}
  const isFormData = options.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), ...authorization, ...(options.headers || {}) },
  })
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
    throw new Error(message)
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
  upload: (formData) => request('/admin/knowledge/documents', { method: 'POST', body: formData }),
  reindex: (id) => request(`/admin/knowledge/documents/${id}/reindex`, { method: 'POST' }),
  remove: (id) => request(`/admin/knowledge/documents/${id}`, { method: 'DELETE' }),
}
