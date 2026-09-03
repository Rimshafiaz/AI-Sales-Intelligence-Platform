import { supabase } from './supabase'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  code: string
  requestId: string | null
  status: number

  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  params?: Record<string, string | number | undefined>
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { data: sessionData } = await supabase.auth.getSession()
  const token = sessionData.session?.access_token

  const url = new URL(path, API_URL)
  if (options.params) {
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }

  const response = await fetch(url, {
    method: options.method ?? 'GET',
    headers: {
      ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (response.status === 204) {
    return undefined as T
  }

  if (!response.ok) {
    let code = 'unknown_error'
    let message = `Request failed with status ${response.status}`
    let requestId: string | null = null
    try {
      const payload = await response.json()
      if (payload.error) {
        code = payload.error.code ?? code
        message = payload.error.message ?? message
        requestId = payload.error.request_id ?? null
      }
    } catch {
      // non-JSON error body; keep defaults
    }
    throw new ApiError(response.status, code, message, requestId)
  }

  return (await response.json()) as T
}
