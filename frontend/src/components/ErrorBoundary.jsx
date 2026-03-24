import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, textAlign: 'center' }}>
          <div style={{ fontSize: 30, marginBottom: 12 }}>⚠️</div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--red)', marginBottom: 8 }}>
            Something went wrong
          </div>
          <div style={{ fontSize: 11, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>
            {this.state.error.message}
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              marginTop: 16, padding: '8px 20px', background: 'var(--bg3)',
              border: '1px solid var(--border2)', color: 'var(--text)',
              borderRadius: 'var(--r)', fontSize: 12, cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
