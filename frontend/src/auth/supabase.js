import { createClient } from '@supabase/supabase-js'

let client

export function getSupabaseClient() {
  if (client) return client
  const environment = import.meta.env || {}
  const processEnvironment = typeof process === 'undefined' ? {} : process.env
  const supabaseUrl = environment.VITE_SUPABASE_URL || processEnvironment.VITE_SUPABASE_URL
  const supabaseAnonKey = environment.VITE_SUPABASE_ANON_KEY || processEnvironment.VITE_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error('VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be configured.')
  }

  client = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: true,
    },
  })
  return client
}
