import { useState, useMemo } from 'react'
import { useApi } from '../../hooks/useApi'
import { getPlayerOdds } from '../../api/client'
import Spinner from '../Spinner'
import FlowGuide from '../FlowGuide'
import { probBg, probTextColor } from '../../utils/prob'

const LABEL = {
  anytimeGoalscorer:   'Anytime Scorer',
  toScore2OrMore:      '2+ Goals',
  toScoreHatTrick:     'Hat-Trick',
  anytimeAssist:       'Anytime Assist',
  toScoreOrAssist:     'Score or Assist',
  goalAssistDouble:    'G+A Double',
  shots1Plus:          '1+ Shots',
  shots2Plus:          '2+ Shots',
  shotsOnTarget1Plus:  '1+ SoT',
  shotsOnTarget2Plus:  '2+ SoT',
  shotsOnTarget3Plus:  '3+ SoT',
}

const SECTIONS = [
  { key: 'goals',         label: 'GOALS',           icon: '⚽', markets: ['anytimeGoalscorer','toScore2OrMore','toScoreHatTrick'],        defaultSort: 'anytimeGoalscorer', isCombo: false },
  { key: 'assists',       label: 'ASSISTS',          icon: '🎯', markets: ['anytimeAssist','toScoreOrAssist'],                             defaultSort: 'anytimeAssist',     isCombo: false },
  { key: 'shots',         label: 'SHOTS',            icon: '💥', markets: ['shots1Plus','shots2Plus'],                                     defaultSort: 'shots1Plus',        isCombo: false },
  { key: 'shotsOnTarget', label: 'SHOTS ON TARGET',  icon: '🥅', markets: ['shotsOnTarget1Plus','shotsOnTarget2Plus','shotsOnTarget3Plus'], defaultSort: 'shotsOnTarget1Plus', isCombo: false },
  { key: 'ga_double',     label: 'G+A DOUBLE',       icon: '🔗', markets: ['goalAssistDouble'],                                            defaultSort: 'goalAssistDouble',   isCombo: true  },
]

const COMBO_RE = /^(.+?) to score a goal assisted by (.+)$/i

export default function PlayersTab({ fixtureId }) {
  const { data, loading, error } = useApi(
    fixtureId ? () => getPlayerOdds(fixtureId) : null,
    [fixtureId]
  )

  const [search,    setSearch]    = useState('')
  const [collapsed, setCollapsed] = useState({ ga_double: true })
  const [sort,      setSort]      = useState(
    Object.fromEntries(SECTIONS.map(s => [s.key, { col: s.defaultSort, dir: 'desc' }]))
  )

  // Reset search when fixture changes
  useMemo(() => { setSearch('') }, [fixtureId])

  if (!fixtureId) {
    return (
      <FlowGuide
        icon="👤"
        title="Select a Fixture"
        steps="<b>Step 1</b> — Select a Competition<br><b>Step 2</b> — Select a Fixture"
      />
    )
  }
  if (loading) return <Spinner />
  if (error)   return <div className="error-box">⚠ {error}</div>
  if (!data?.length) return <FlowGuide icon="⚠️" title="No player market data for this fixture" />

  const q        = search.toLowerCase().trim()
  const filtered = q ? data.filter(p => p.playerName?.toLowerCase().includes(q)) : data
  const covered  = new Set(data.flatMap(p => Object.keys(p.markets || {})))

  function toggleCollapse(key) {
    setCollapsed(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function handleSort(secKey, col) {
    setSort(prev => {
      const cur = prev[secKey]
      return { ...prev, [secKey]: { col, dir: cur.col === col ? (cur.dir === 'desc' ? 'asc' : 'desc') : 'desc' } }
    })
  }

  return (
    <div>
      <div className="player-search-bar">
        <input
          className="p-search"
          placeholder="🔍  Search player…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <span className="p-count">{filtered.length} players</span>
      </div>

      {SECTIONS.map(sec => {
        const activeMkts = sec.markets.filter(mk => covered.has(mk))
        const isCollapsed = collapsed[sec.key] ?? false

        if (sec.isCombo) {
          return (
            <ComboSection
              key={sec.key}
              sec={sec}
              data={data}
              query={q}
              activeMkts={activeMkts}
              isCollapsed={isCollapsed}
              onToggle={() => toggleCollapse(sec.key)}
            />
          )
        }

        const secPlayers = filtered.filter(p => activeMkts.some(mk => p.markets?.[mk] != null))
        const { col, dir } = sort[sec.key]
        const sorted = [...secPlayers].sort((a, b) => {
          const va = a.markets?.[col] ?? -1
          const vb = b.markets?.[col] ?? -1
          return dir === 'desc' ? vb - va : va - vb
        })

        return (
          <div key={sec.key} className={`mkt-section${isCollapsed ? ' collapsed' : ''}`}>
            <div className="mkt-section-hd" onClick={() => toggleCollapse(sec.key)}>
              <span className="mkt-icon">{sec.icon}</span>
              <span className="mkt-title">{sec.label}</span>
              <span className="mkt-count">{secPlayers.length} players</span>
              <span className="mkt-chevron">▼</span>
            </div>
            <div className="mkt-section-body">
              {activeMkts.length === 0 ? (
                <div style={{ padding: '16px 14px', fontSize: 10, color: 'var(--faint)' }}>
                  No {sec.label.toLowerCase()} data for this fixture
                </div>
              ) : (
                <div className="mkt-table-wrap">
                  <table className="mkt-table">
                    <thead>
                      <tr>
                        <th>Player</th>
                        {activeMkts.map(mk => (
                          <th
                            key={mk}
                            className={col === mk ? (dir === 'desc' ? 's-desc' : 's-asc') : ''}
                            onClick={() => handleSort(sec.key, mk)}
                          >
                            {LABEL[mk] ?? mk}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sorted.map(p => (
                        <tr key={p.selectionId}>
                          <td>
                            <div className="p-name-cell">
                              {p.logo
                                ? <img className="p-logo" src={p.logo} alt="" onError={e => (e.target.style.display = 'none')} />
                                : <div className="p-logo-ph">{p.playerName?.slice(0, 2).toUpperCase()}</div>
                              }
                              <span>{p.playerName}</span>
                            </div>
                          </td>
                          {activeMkts.map(mk => {
                            const v = p.markets?.[mk]
                            if (v == null) return <td key={mk} className="prob-cell prob-null">—</td>
                            return (
                              <td
                                key={mk}
                                className="prob-cell"
                                style={{ background: probBg(v), color: probTextColor(v) }}
                              >
                                {v.toFixed(1)}%
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )
      })}

      {/* GK Saves — static notice (not in FanDuel UCL feed) */}
      <div className="mkt-section">
        <div className="mkt-section-hd" style={{ cursor: 'default' }}>
          <span className="mkt-icon">🧤</span>
          <span className="mkt-title">Saves / GK</span>
          <span className="mkt-count" style={{ color: 'var(--faint)' }}>unavailable</span>
        </div>
        <div className="mkt-section-body">
          <div className="gk-notice">
            <div className="gk-notice-icon">ℹ️</div>
            <div className="gk-notice-text">
              <strong>GK Saves market not in this dataset</strong>
              FanDuel does not include GK Saves (3+) in their UEFA Champions League event markets.
              This section will populate automatically if the market becomes available in the source feed.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ComboSection({ sec, data, query, activeMkts, isCollapsed, onToggle }) {
  if (activeMkts.length === 0) {
    return (
      <div className="mkt-section">
        <div className="mkt-section-hd" style={{ cursor: 'default' }}>
          <span className="mkt-icon">{sec.icon}</span>
          <span className="mkt-title">{sec.label}</span>
          <span className="mkt-count" style={{ color: 'var(--faint)' }}>not in this fixture</span>
        </div>
      </div>
    )
  }

  const combos = data
    .filter(p => p.markets?.goalAssistDouble != null)
    .map(p => {
      const m = COMBO_RE.exec(p.playerName)
      return m
        ? { scorer: m[1], assister: m[2], prob: p.markets.goalAssistDouble }
        : { scorer: p.playerName, assister: '—', prob: p.markets.goalAssistDouble }
    })
    .filter(c => !query || c.scorer.toLowerCase().includes(query) || c.assister.toLowerCase().includes(query))
    .sort((a, b) => b.prob - a.prob)

  return (
    <div className={`mkt-section${isCollapsed ? ' collapsed' : ''}`}>
      <div className="mkt-section-hd" onClick={onToggle}>
        <span className="mkt-icon">{sec.icon}</span>
        <span className="mkt-title">{sec.label}</span>
        <span className="mkt-count">{combos.length} pairs</span>
        <span className="mkt-chevron">▼</span>
      </div>
      <div className="mkt-section-body">
        <div className="combo-table-wrap">
          <table className="combo-table">
            <thead>
              <tr>
                <th>⚽ Scorer</th>
                <th>🎯 Assister</th>
                <th className="prob-col">Prob</th>
              </tr>
            </thead>
            <tbody>
              {combos.map((c, i) => (
                <tr key={i}>
                  <td>
                    <div className="combo-player">{c.scorer}</div>
                    <div className="combo-role">Scorer</div>
                  </td>
                  <td>
                    <div className="combo-player">{c.assister}</div>
                    <div className="combo-role">Assister</div>
                  </td>
                  <td
                    className="prob-col"
                    style={{ background: probBg(c.prob), color: probTextColor(c.prob) }}
                  >
                    {c.prob.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
