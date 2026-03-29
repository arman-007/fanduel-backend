import { useState } from 'react'
import { login } from '../api/client'

export default function LoginScreen({ onLogin }) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState(null)
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await login(email, password)
      onLogin(data.email)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.wrapper}>
      <form onSubmit={handleSubmit} style={styles.card}>
        <div style={styles.logoRow}>
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: 32, height: 32 }}>
            <circle cx="12" cy="12" r="9.5" stroke="var(--accent)" strokeWidth="1.5"/>
            <polygon points="12,3.5 14,8.8 19.8,9.2 15.5,13 17,18.5 12,15.5 7,18.5 8.5,13 4.2,9.2 10,8.8" fill="var(--accent)"/>
          </svg>
          <div>
            <div style={styles.logoText}>SPORTINERD</div>
            <div style={styles.logoSub}>Odds Explorer</div>
          </div>
        </div>

        <label style={styles.label}>Email</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          autoFocus
          style={styles.input}
          placeholder="you@example.com"
        />

        <label style={styles.label}>Password</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          style={styles.input}
          placeholder="Enter password"
        />

        {error && <div style={styles.error}>{error}</div>}

        <button type="submit" disabled={loading} style={styles.btn}>
          {loading ? 'Logging in...' : 'Log In'}
        </button>
      </form>
    </div>
  )
}

const styles = {
  wrapper: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    minHeight: '100vh', padding: 16,
  },
  card: {
    background: 'var(--bg2)', border: '1px solid var(--border)',
    borderRadius: 'var(--r)', padding: '32px 28px', width: '100%', maxWidth: 380,
    display: 'flex', flexDirection: 'column', gap: 12,
  },
  logoRow: {
    display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8,
  },
  logoText: {
    fontFamily: 'var(--ui)', fontWeight: 700, fontSize: 16, color: 'var(--text)',
    letterSpacing: '0.12em',
  },
  logoSub: {
    fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--dim)',
    letterSpacing: '0.08em', textTransform: 'uppercase',
  },
  label: {
    fontSize: 11, color: 'var(--dim)', textTransform: 'uppercase',
    letterSpacing: '0.06em', fontFamily: 'var(--mono)',
  },
  input: {
    background: 'var(--bg3)', border: '1px solid var(--border)',
    borderRadius: 'var(--r)', padding: '10px 12px', fontSize: 14,
    color: 'var(--text)', outline: 'none', width: '100%',
  },
  error: {
    background: 'rgba(255,77,109,0.1)', border: '1px solid var(--red)',
    borderRadius: 'var(--r)', padding: '8px 12px', fontSize: 12,
    color: 'var(--red)', fontFamily: 'var(--mono)',
  },
  btn: {
    background: 'var(--accent)', color: '#070e1c', border: 'none',
    borderRadius: 'var(--r)', padding: '10px 0', fontSize: 14,
    fontWeight: 700, cursor: 'pointer', marginTop: 4,
    letterSpacing: '0.04em',
  },
}
