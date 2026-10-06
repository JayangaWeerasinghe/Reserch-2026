import api from './api'

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface ProfileResponse {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post('/api/v1/auth/login', { email, password })
  return data
}

export async function register(email: string, password: string, fullName?: string): Promise<TokenResponse> {
  const { data } = await api.post('/api/v1/auth/register', { email, password, full_name: fullName || null })
  return data
}

export async function getProfile(): Promise<ProfileResponse> {
  const { data } = await api.get('/api/v1/auth/me')
  return data
}
