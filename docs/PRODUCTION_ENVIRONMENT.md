# Production environment configuration

## Backend (Render or Railway)

Configure these values on the backend service:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` — server-side only; never set a `VITE_` prefix on this value.
- `MONGODB_URI`
- `MONGODB_DATABASE`
- `GROQ_API_KEY`
- `GOOGLE_API_KEY`
- `TAVILY_API_KEY`
- `OPENWEATHERMAP_API_KEY`
- `EXCHANGE_RATE_API_KEY`
- `PACK_GO_ALLOWED_ORIGINS` — comma-separated frontend origins.
- `PACK_GO_ENV=production`

The `create_admin.py` operator script grants admin access to an existing Supabase Auth UUID supplied as `SUPABASE_USER_ID`.

## Frontend (Vercel)

Configure these values as build-time environment variables:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY` — the public anon/publishable key.
- `VITE_API_BASE_URL` — deployed backend origin, for example `https://api.example.com`.

Leaving `VITE_API_BASE_URL` empty uses the Vite `/api/v1` and `/plan` development proxies. Do not configure or expose backend service-role or other server secrets in Vercel frontend variables.
