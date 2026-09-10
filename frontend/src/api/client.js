const API_BASE = '/api/v1'
const LEGACY_PLAN_ERROR = 'Unable to generate the travel plan at this time. Please try again.'

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
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = body.detail || body.error
    const message = path.startsWith('/auth/')
      ? authErrorMessage(path, detail)
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
}
