import { useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { AuthContext } from './context'
const USER_KEY = 'pack-go-user'
const TOKEN_KEY = 'pack-go-token'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem(USER_KEY) || 'null'))
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  }, [user, token])

  const authenticate = async (action, payload) => {
    setIsLoading(true)
    try {
      const result = await action(payload)
      setUser(result.user)
      setToken(result.access_token)
      return result
    } finally {
      setIsLoading(false)
    }
  }

  const login = (payload) => authenticate(authApi.login, payload)
  const register = (payload) => authenticate(authApi.register, payload)
  const logout = async () => {
    if (token) await authApi.logout(token).catch(() => {})
    setUser(null)
    setToken(null)
  }

  return <AuthContext.Provider value={{ user, token, isAuthenticated: Boolean(token), isLoading, login, register, logout }}>{children}</AuthContext.Provider>
}

