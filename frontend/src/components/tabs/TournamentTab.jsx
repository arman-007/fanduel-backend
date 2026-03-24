import { useApi } from '../../hooks/useApi'
import { getTournamentOdds } from '../../api/client'
import Spinner from '../Spinner'
import FlowGuide from '../FlowGuide'

export default function TournamentTab({ competitionId }) {
  const { data, loading, error } = useApi(
    competitionId ? () => getTournamentOdds(competitionId) : null,
    [competitionId]
  )

  if (!competitionId) {
    return <FlowGuide icon="🏆" title="Select a Competition" steps="Use the <b>Competition</b> dropdown above." />
  }
  if (loading) return <Spinner />
  if (error)   return <div className="error-box">⚠ {error}</div>
  if (!data)   return <FlowGuide icon="⚠️" title="No tournament data" />

  const maxP = arr => (arr?.length ? Math.max(...arr.map(x => x.probability)) : 1)

  return (
    <div className="t-grid">
      <TCard title="🥇 Competition Winner"  runners={data.champion}  maxP={maxP(data.champion)}  note={null} />
      <TCard title="🥈 To Reach The Final"  runners={data.runnerUp}  maxP={maxP(data.runnerUp)}  note={data.runnerUpNote} />
      <TCard title="⚽ Top Goalscorer"      runners={data.topScorer} maxP={maxP(data.topScorer)} note={null} />
    </div>
  )
}

function TCard({ title, runners, maxP, note }) {
  const flag = note
    ? (
      <span className="tooltip-wrap">
        <span className="proxy-flag">⚠ PROXY</span>
        <span className="tip">{note}</span>
      </span>
    )
    : null

  return (
    <div className="t-card">
      <div className="t-card-title">
        {title}
        {flag}
      </div>
      {(!runners || runners.length === 0) && (
        <div style={{ fontSize: 10, color: 'var(--faint)', padding: '8px 0' }}>No data available</div>
      )}
      {runners?.slice(0, 16).map((r, i) => {
        const rankCls = i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : ''
        const barW = Math.round((r.probability / maxP) * 100)
        return (
          <div key={r.selectionId ?? i} className={`bar-row ${rankCls}`}>
            <div className="bar-rank">{i + 1}</div>
            {r.logo
              ? <img className="bar-logo" src={r.logo} alt="" onError={e => (e.target.style.display = 'none')} />
              : <div className="bar-ph">{r.name?.slice(0, 2).toUpperCase()}</div>
            }
            <div className="bar-name">{r.name}</div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${barW}%` }} />
            </div>
            <div className="bar-pct">{r.probability?.toFixed(1)}%</div>
          </div>
        )
      })}
    </div>
  )
}
