const BASE = '/api'

async function apiFetch(path) {
  let res
  try {
    res = await fetch(BASE + path)
  } catch (err) {
    throw new Error(`Network error — could not reach the API. Is the server running? (${err.message})`)
  }
  if (!res.ok) {
    let detail = ''
    try { const body = await res.json(); detail = body.detail || '' } catch (_) {}
    throw new Error(`API ${res.status}: ${detail || res.statusText}`)
  }
  return res.json()
}

export const getCompetitions  = ()             => apiFetch('/competitions')
export const getFixtures       = (competitionId) => apiFetch(`/fixtures?competition_id=${competitionId}`)
export const getTournamentOdds = (competitionId) => apiFetch(`/tournament-odds?competition_id=${competitionId}`)
export const getMatchOdds      = (fixtureId)     => apiFetch(`/match-odds?fixture_id=${fixtureId}`)
export const getPlayerOdds     = (fixtureId)     => apiFetch(`/player-odds?fixture_id=${fixtureId}`)
export const getPredictions    = (fixtureId)     => apiFetch(`/predictions?fixture_id=${fixtureId}`)
