import { useApi } from '../../hooks/useApi'
import { getMatchOdds } from '../../api/client'
import Spinner from '../Spinner'
import FlowGuide from '../FlowGuide'
import { csHeatColor } from '../../utils/prob'

export default function MatchTab({ fixtureId, fixtures }) {
  const { data, loading, error } = useApi(
    fixtureId ? () => getMatchOdds(fixtureId) : null,
    [fixtureId]
  )

  if (!fixtureId) {
    return (
      <FlowGuide
        icon="⚽"
        title="Select a Fixture"
        steps="<b>Step 1</b> — Select a Competition<br><b>Step 2</b> — Select a Fixture"
      />
    )
  }
  if (loading) return <Spinner />
  if (error)   return <div className="error-box">⚠ {error}</div>
  if (!data?.wdw?.length) return <FlowGuide icon="⚠️" title="No match odds data for this fixture" />

  const maxW = Math.max(...data.wdw.map(w => w.probability))

  // Resolve label for each WDW runner
  function wdwLabel(runner) {
    if (runner.name === 'Draw') return 'Draw'
    if (runner.name === data.homeTeam) return 'Home Win'
    return 'Away Win'
  }

  // Format matchDate
  const fixture = fixtures?.find(f => f.fixtureId === fixtureId)
  const matchDate = fixture?.matchDate
    ? new Date(fixture.matchDate).toLocaleString('en-GB', {
        weekday: 'short', day: '2-digit', month: 'short',
        hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
      }) + ' UTC'
    : ''

  return (
    <div>
      <div className="match-hero">
        <div className="match-hero-top">
          <div className="match-name">{data.name}</div>
        </div>
        <div className="match-meta">
          {matchDate && <span className="match-date">{matchDate}</span>}
          <span className="match-note">Normalised (bookmaker margin removed)</span>
        </div>
      </div>

      {/* WDW */}
      <div className="panel-box" style={{ marginBottom: 14 }}>
        <div className="section-hd" style={{ marginTop: 0 }}>Win / Draw / Win</div>
        <div className="wdw-cards">
          {data.wdw.map(w => {
            const isFav = w.probability === maxW
            const barW  = Math.round((w.probability / maxW) * 100)
            return (
              <div key={w.selectionId} className={`wdw-card${isFav ? ' fav' : ''}`}>
                <div className="wdw-card-label">{wdwLabel(w)}</div>
                <div className="wdw-card-team">{w.name}</div>
                <div className="wdw-card-prob">{w.probability?.toFixed(1)}</div>
                <div className="wdw-card-unit">%</div>
                <div className="wdw-card-bar">
                  <div className="wdw-card-bar-fill" style={{ width: `${barW}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Correct Score Matrix */}
      <div className="panel-box">
        <div className="section-hd" style={{ marginTop: 0 }}>Correct Score</div>
        <div className="cs-note">Cell = normalised probability %. Colour = relative likelihood.</div>
        <CSMatrix scores={data.correctScore} home={data.homeTeam} away={data.awayTeam} />
      </div>
    </div>
  )
}

function CSMatrix({ scores, home, away }) {
  if (!scores?.length) {
    return <div style={{ color: 'var(--faint)', padding: 14, fontSize: 11 }}>No correct score data</div>
  }

  let maxH = 0, maxA = 0
  const map = {}
  const probs = []

  scores.forEach(s => {
    if (s.scoreHome == null) return
    maxH = Math.max(maxH, s.scoreHome)
    maxA = Math.max(maxA, s.scoreAway)
    map[`${s.scoreHome}-${s.scoreAway}`] = s.probability
    probs.push(s.probability)
  })

  const maxP  = Math.max(...probs)
  const homeShort = home?.split(' ').pop() ?? 'Home'
  const awayShort = away?.split(' ').pop() ?? 'Away'

  const cols = Array.from({ length: maxA + 1 }, (_, i) => i)
  const rows = Array.from({ length: maxH + 1 }, (_, i) => i)

  return (
    <div className="cs-wrap">
      <table className="cs-table">
        <thead>
          <tr>
            <th className="sticky-col">{homeShort} ↓ / {awayShort} →</th>
            {cols.map(a => <th key={a}>{a}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r}>
              <td className="row-lbl">{r} — {homeShort}</td>
              {cols.map(a => {
                const p = map[`${r}-${a}`]
                if (p === undefined) {
                  return <td key={a} style={{ color: 'var(--faint)' }}>—</td>
                }
                const t  = p / maxP
                const bg = csHeatColor(t)
                const tc = t > 0.5 ? '#fff' : t > 0.25 ? 'var(--text)' : 'var(--dim)'
                return (
                  <td key={a} style={{ background: bg, color: tc }}>
                    {p.toFixed(2)}%
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
