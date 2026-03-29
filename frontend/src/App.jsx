import { useState, useEffect } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import LoginScreen from './components/LoginScreen'
import Spinner from './components/Spinner'
import TournamentTab from './components/tabs/TournamentTab'
import MatchTab from './components/tabs/MatchTab'
import PlayersTab from './components/tabs/PlayersTab'
import PredictionsTab from './components/tabs/PredictionsTab'
import { getCompetitions, getFixtures, checkAuth, logout } from './api/client'

const TABS = [
  { key: 'tournament', icon: '🏆', label: 'Tournament' },
  { key: 'match',      icon: '⚽', label: 'Match Odds' },
  { key: 'players',    icon: '👤', label: 'Player Markets' },
  { key: 'predictions',icon: '🔮', label: 'Predictions' },
]

export default function App() {
  const [user,          setUser]          = useState(null)
  const [authChecked,   setAuthChecked]   = useState(false)
  const [activeTab,     setActiveTab]     = useState('tournament')
  const [competitionId, setCompetitionId] = useState(null)
  const [fixtureId,     setFixtureId]     = useState(null)

  const [competitions,      setCompetitions]      = useState([])
  const [fixtures,          setFixtures]          = useState([])
  const [loadingComps,      setLoadingComps]      = useState(true)
  const [loadingFixtures,   setLoadingFixtures]   = useState(false)
  const [compError,         setCompError]         = useState(null)
  const [fixtureError,      setFixtureError]      = useState(null)

  // Check session on mount
  useEffect(() => {
    checkAuth()
      .then(data => setUser(data.email))
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  // Load competitions once authenticated
  useEffect(() => {
    if (!user) return
    setLoadingComps(true)
    getCompetitions()
      .then(data => { setCompetitions(data); setLoadingComps(false) })
      .catch(err  => { setCompError(err.message); setLoadingComps(false) })
  }, [user])

  // Load fixtures when competition changes
  useEffect(() => {
    if (!competitionId) { setFixtures([]); setFixtureId(null); return }
    setLoadingFixtures(true)
    setFixtures([])
    setFixtureId(null)
    getFixtures(competitionId)
      .then(data => { setFixtures(data); setLoadingFixtures(false) })
      .catch(err  => { setFixtureError(err.message); setLoadingFixtures(false) })
  }, [competitionId])

  function handleCompetitionChange(id) {
    setCompetitionId(id ? Number(id) : null)
    setFixtureId(null)
  }

  function handleFixtureChange(id) {
    setFixtureId(id ? Number(id) : null)
  }

  const selects = (
    <>
      <div className="sel-group">
        <div className="sel-label">Competition</div>
        <select
          value={competitionId ?? ''}
          onChange={e => handleCompetitionChange(e.target.value)}
          disabled={loadingComps}
        >
          <option value="">— Select Competition —</option>
          {competitions.map(c => (
            <option key={c.competitionId} value={c.competitionId}>
              {c.name}  ({c.fixtureCount})
            </option>
          ))}
        </select>
      </div>
      <div className="sel-group">
        <div className="sel-label">Fixture</div>
        <select
          value={fixtureId ?? ''}
          onChange={e => handleFixtureChange(e.target.value)}
          disabled={!competitionId || loadingFixtures}
        >
          <option value="">— Select Fixture —</option>
          {fixtures.map(f => {
            const d = f.matchDate ? new Date(f.matchDate) : null
            const dateStr = d
              ? d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'
              : ''
            return (
              <option key={f.fixtureId} value={f.fixtureId}>
                {f.name}{dateStr ? `  —  ${dateStr}` : ''}
              </option>
            )
          })}
        </select>
      </div>
    </>
  )

  async function handleLogout() {
    await logout()
    setUser(null)
    setCompetitions([])
    setFixtures([])
    setCompetitionId(null)
    setFixtureId(null)
  }

  if (!authChecked) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}><Spinner /></div>
  if (!user) return <LoginScreen onLogin={email => setUser(email)} />

  return (
    <ErrorBoundary>
      {/* ── HEADER ── */}
      <header className="header">
        <div className="header-row1">
          <div className="logo">
            <div className="logo-icon">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="9.5" stroke="#07101e" strokeWidth="1.5"/>
                <polygon points="12,3.5 14,8.8 19.8,9.2 15.5,13 17,18.5 12,15.5 7,18.5 8.5,13 4.2,9.2 10,8.8" fill="#07101e"/>
              </svg>
            </div>
            <div>
              <div className="logo-text">SPORTINERD</div>
              <div className="logo-sub">Odds Explorer</div>
            </div>
          </div>

          <div className="header-selects">
            {loadingComps
              ? <Spinner />
              : compError
                ? <span style={{ fontSize: 11, color: 'var(--red)' }}>⚠ {compError}</span>
                : selects
            }
          </div>

          <div className="header-meta">
            <span className="snap-time">{new Date().toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
            <span className="mode-badge">LIVE</span>
            <button onClick={handleLogout} style={{ marginLeft: 8, padding: '4px 10px', fontSize: 11, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 'var(--r)', color: 'var(--dim)', cursor: 'pointer' }}>Logout</button>
          </div>
        </div>

        {/* Mobile row */}
        <div className="header-row2">
          {!loadingComps && !compError && selects}
        </div>
      </header>

      {/* ── DESKTOP TABS ── */}
      <div className="tabs-bar">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`tab-btn${activeTab === t.key ? ' active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── CONTENT ── */}
      <div className="content">
        {activeTab === 'tournament' && (
          <div className="tab-panel">
            <TournamentTab competitionId={competitionId} />
          </div>
        )}
        {activeTab === 'match' && (
          <div className="tab-panel">
            <MatchTab fixtureId={fixtureId} fixtures={fixtures} />
          </div>
        )}
        {activeTab === 'players' && (
          <div className="tab-panel">
            <PlayersTab fixtureId={fixtureId} />
          </div>
        )}
        {activeTab === 'predictions' && (
          <div className="tab-panel">
            <PredictionsTab fixtureId={fixtureId} />
          </div>
        )}
      </div>

      {/* ── BOTTOM NAV (mobile) ── */}
      <nav className="bottom-nav">
        <div className="bottom-nav-inner">
          {TABS.map(t => (
            <button
              key={t.key}
              className={`bnav-btn${activeTab === t.key ? ' active' : ''}`}
              onClick={() => setActiveTab(t.key)}
            >
              <div className="bnav-icon">{t.icon}</div>
              <div className="bnav-label">{t.label.split(' ')[0]}</div>
            </button>
          ))}
        </div>
      </nav>
    </ErrorBoundary>
  )
}
