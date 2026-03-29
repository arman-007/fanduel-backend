const BASE = '/api'
const AUTH_BASE = '/auth'

async function apiFetch(path) {
  let res
  try {
    res = await fetch(BASE + path, { credentials: 'include' })
  } catch (err) {
    throw new Error(`Network error — could not reach the API. Is the server running? (${err.message})`)
  }
  if (res.status === 401) {
    throw new Error('__AUTH_REQUIRED__')
  }
  if (!res.ok) {
    let detail = ''
    try { const body = await res.json(); detail = body.detail || '' } catch (_) {}
    throw new Error(`API ${res.status}: ${detail || res.statusText}`)
  }
  return res.json()
}

// Auth
export async function login(email, password) {
  const res = await fetch(AUTH_BASE + '/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    let detail = 'Invalid email or password'
    try { const body = await res.json(); detail = body.detail || detail } catch (_) {}
    throw new Error(detail)
  }
  return res.json()
}

export async function logout() {
  await fetch(AUTH_BASE + '/logout', { method: 'POST', credentials: 'include' })
}

export async function checkAuth() {
  const res = await fetch(AUTH_BASE + '/me', { credentials: 'include' })
  if (!res.ok) throw new Error('Not authenticated')
  return res.json()
}

// Data
export const getCompetitions  = ()             => apiFetch('/competitions')
export const getFixtures       = (competitionId) => apiFetch(`/fixtures?competition_id=${competitionId}`)
export const getTournamentOdds = (competitionId) => apiFetch(`/tournament-odds?competition_id=${competitionId}`)
export const getMatchOdds      = (fixtureId)     => apiFetch(`/match-odds?fixture_id=${fixtureId}`)
export const getPlayerOdds     = (fixtureId)     => apiFetch(`/player-odds?fixture_id=${fixtureId}`)
export const getPredictions    = (fixtureId)     => apiFetch(`/predictions?fixture_id=${fixtureId}`)
