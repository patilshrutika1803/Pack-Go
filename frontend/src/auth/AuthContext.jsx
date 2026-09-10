import { useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { AuthContext } from './context'
const USER_KEY = 'pack-go-user'
const TOKEN_KEY = 'pack-go-token'
const REFRESH_KEY = 'pack-go-refresh-token'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem(USER_KEY) || 'null'))
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem(REFRESH_KEY))
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
    if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken)
    else localStorage.removeItem(REFRESH_KEY)
  }, [user, token, refreshToken])

  useEffect(() => {
    let active = true
    async function restore() {
      if (!token && !refreshToken) return setIsLoading(false)
      try {
        const result = token ? await authApi.me(token) : await authApi.refresh(refreshToken)
        if (!active) return
        setUser(result.user || result)
        if (result.access_token) setToken(result.access_token)
        if (result.refresh_token) setRefreshToken(result.refresh_token)
      } catch {
        if (!refreshToken) {
          setUser(null)
          setToken(null)
        } else {
          try {
            const result = await authApi.refresh(refreshToken)
            if (!active) return
            setUser(result.user)
            setToken(result.access_token)
            setRefreshToken(result.refresh_token)
          } catch {
            setUser(null)
            setToken(null)
            setRefreshToken(null)
          }
        }
      } finally {
        if (active) setIsLoading(false)
      }
    }
    restore()
    return () => { active = false }
  }, [token, refreshToken])

  const authenticate = async (action, payload) => {
    setIsLoading(true)
    try {
      const result = await action(payload)
      setUser(result.user)
      setToken(result.access_token)
      setRefreshToken(result.refresh_token)
      return result
    } finally {
      setIsLoading(false)
    }
  }

  const login = (payload) => authenticate(authApi.login, payload)
  const register = (payload) => authenticate(authApi.register, payload)
  const logout = async () => {
    if (refreshToken) await authApi.logout(refreshToken).catch(() => {})
    setUser(null)
    setToken(null)
    setRefreshToken(null)
  }

  return <AuthContext.Provider value={{ user, token, refreshToken, isAuthenticated: Boolean(user && token), isLoading, login, register, logout }}>{children}</AuthContext.Provider>
}

