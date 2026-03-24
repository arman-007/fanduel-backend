import { useApi } from '../../hooks/useApi'
import { getPredictions } from '../../api/client'
import Spinner from '../Spinner'
import FlowGuide from '../FlowGuide'
import { probBg, probTextColor } from '../../utils/prob'

const OU_ROWS = [
  ['Over 0.5', 'over05'],
  ['Over 1.5', 'over15'],
  ['Over 2.5', 'over25'],
  ['Over 3.5', 'over35'],
  ['Over 4.5', 'over45'],
]

export default function PredictionsTab({ fixtureId }) {
  const { data, loading, error } = useApi(
    fixtureId ? () => getPredictions(fixtureId) : null,
    [fixtureId]
  )

  if (!fixtureId) {
    return (
      <FlowGuide
        icon="🔮"
        title="Select a Fixture"
        steps="<b>Step 1</b> — Select a Competition<br><b>Step 2</b> — Select a Fixture"
      />
    )
  }
  if (loading) return <Spinner />
  if (error)   return <div className="error-box">⚠ {error}</div>
  if (!data)   return <FlowGuide icon="⚠️" title="No predictions for this fixture" />

  const m      = data.match  || {}
  const ou     = m.overUnder || {}
  const combos = data.combos || {}
  const pairs  = combos.pairs || []
  const isFeed = combos.source === 'feed'

  const xgH = m.xGHome?.value ?? null
  const xgA = m.xGAway?.value ?? null

  return (
    <div>
      {/* Header */}
      <div className="panel-box pred-header" style={{ marginBottom: 14 }}>
        <div className="match-name">{data.homeTeam} vs {data.awayTeam}</div>
        <div className="pred-header-note">
          All values are normalised probabilities derived from FanDuel market data.
        </div>
      </div>

      {/* xG row */}
      <div className="pred-xg-row">
        <div className="pred-xg-team">
          <div className="pred-xg-name">{data.homeTeam || 'Home'}</div>
          <div className="pred-xg-val">{xgH != null ? xgH.toFixed(2) : '—'}</div>
          <div className="pred-xg-lbl">xG</div>
        </div>
        <div className="pred-xg-vs">vs</div>
        <div className="pred-xg-team">
          <div className="pred-xg-name">{data.awayTeam || 'Away'}</div>
          <div className="pred-xg-val">{xgA != null ? xgA.toFixed(2) : '—'}</div>
          <div className="pred-xg-lbl">xG</div>
        </div>
      </div>

      {/* Stats grid: BTTS / Home CS / Away CS */}
      <div className="pred-stats-grid">
        <StatCard label="BTTS"             value={(m.btts?.value            ?? 0).toFixed(1)} unit="%" method="cs_matrix" />
        <StatCard label="Home Clean Sheet" value={(m.homeCleanSheet?.value  ?? 0).toFixed(1)} unit="%" method="cs_matrix" />
        <StatCard label="Away Clean Sheet" value={(m.awayCleanSheet?.value  ?? 0).toFixed(1)} unit="%" method="cs_matrix" />
      </div>

      {/* Over / Under */}
      <div className="panel-box pred-section">
        <div className="section-hd" style={{ marginTop: 0 }}>Over / Under Goals</div>
        <table className="ou-table">
          <tbody>
            {OU_ROWS.map(([label, key]) => {
              const v   = ou[key]?.value ?? 0
              const bar = Math.round(v)
              return (
                <tr key={key}>
                  <td className="ou-label">{label}</td>
                  <td className="ou-bar-cell">
                    <div className="ou-bar-track">
                      <div className="ou-bar-fill" style={{ width: `${bar}%` }} />
                    </div>
                  </td>
                  <td
                    className="ou-pct"
                    style={{ background: probBg(v), color: probTextColor(v) }}
                  >
                    {v.toFixed(1)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="pred-source-note">source: cs_matrix — derived from Correct Score market</div>
      </div>

      {/* GK Saves */}
      {data.gkSaves?.length > 0 && (
        <div className="panel-box pred-section">
          <div className="section-hd" style={{ marginTop: 0 }}>GK Saves (3+)</div>
          <div className="gk-grid">
            {data.gkSaves.map(gk => {
              const p = gk.prob3Plus ?? 0
              return (
                <div key={gk.teamName} className="gk-row">
                  <div className="gk-team">
                    {gk.teamName} <span className="gk-role">GK</span>
                  </div>
                  <div className="gk-stat">xG Against: <b>{gk.xGAgainst?.toFixed(2)}</b></div>
                  <div className="gk-stat">Exp. Saves: <b>{gk.expectedSaves?.toFixed(2)}</b></div>
                  <div
                    className="gk-prob"
                    style={{ background: probBg(p), color: probTextColor(p) }}
                  >
                    3+ Saves: {p.toFixed(1)}%
                  </div>
                </div>
              )
            })}
          </div>
          <div className="pred-source-note">
            source: poisson_xg · MEDIUM confidence · assumes 35% SoT→goal conversion
          </div>
        </div>
      )}

      {/* G+A Combos */}
      {isFeed && pairs.length === 0 ? (
        <div className="panel-box pred-section">
          <div className="section-hd" style={{ marginTop: 0 }}>G+A Combos</div>
          <div className="gk-notice">
            <div className="gk-notice-icon">ℹ️</div>
            <div className="gk-notice-text">
              <strong>Feed data available but empty</strong>
              FanDuel GOALSCORER_ASSIST_DOUBLE market returned no active runners.
            </div>
          </div>
        </div>
      ) : pairs.length > 0 ? (
        <div className="panel-box pred-section">
          <div className="section-hd" style={{ marginTop: 0 }}>G+A Combos</div>
          <div className="combo-table-wrap">
            <table className="combo-table">
              <thead>
                <tr>
                  <th style={{ width: 32 }}>#</th>
                  <th>⚽ Scorer</th>
                  <th>🎯 Assister</th>
                  <th className="prob-col">Prob</th>
                </tr>
              </thead>
              <tbody>
                {pairs.slice(0, 20).map((c, i) => {
                  const p = c.probability ?? 0
                  return (
                    <tr key={i}>
                      <td className="combo-rank">{i + 1}</td>
                      <td>
                        <div className="combo-player">{c.scorerName}</div>
                        <div className="combo-role">Scorer</div>
                      </td>
                      <td>
                        <div className="combo-player">{c.assisterName}</div>
                        <div className="combo-role">Assister</div>
                      </td>
                      <td
                        className="prob-col"
                        style={{ background: probBg(p), color: probTextColor(p) }}
                      >
                        {p.toFixed(1)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="pred-source-note">
            {isFeed
              ? 'source: feed — direct from FanDuel GOALSCORER_ASSIST_DOUBLE market'
              : 'source: independence_approximation · LOW confidence · scorer×assister treated as independent'
            }
          </div>
        </div>
      ) : null}
    </div>
  )
}

function StatCard({ label, value, unit, method }) {
  return (
    <div className="pred-stat-card">
      <div className="pred-stat-label">{label}</div>
      <div className="pred-stat-value">
        {value}<span className="pred-stat-unit">{unit}</span>
      </div>
      <div
        className="pred-stat-method"
        style={{ background: 'rgba(0,212,170,0.12)' }}
      >
        ✓ DERIVED · {method}
      </div>
    </div>
  )
}
