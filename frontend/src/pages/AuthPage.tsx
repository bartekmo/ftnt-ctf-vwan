import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Shield, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

type Mode = 'login' | 'register'

export default function AuthPage({ mode }: { mode: Mode }) {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      let res
      if (mode === 'login') {
        res = await authApi.login(username, password)
      } else {
        res = await authApi.register({ username, email, password })
      }
      setAuth(res.data.user, res.data.access_token)
      navigate('/challenges')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail ?? 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      background: `
        radial-gradient(ellipse at 30% 20%, rgba(229,40,30,0.12) 0%, transparent 50%),
        radial-gradient(ellipse at 70% 80%, rgba(0,212,212,0.08) 0%, transparent 50%),
        var(--color-bg)
      `,
    }}>
      <div style={{ width: '100%', maxWidth: '420px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{
            width: 64, height: 64,
            background: 'linear-gradient(135deg, var(--color-red) 0%, #8b1510 100%)',
            borderRadius: '16px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 1.25rem',
            boxShadow: 'var(--shadow-red)',
          }}>
            <Shield size={32} color="white" />
          </div>
          <h1 style={{ marginBottom: '0.25rem' }}>
            XPERTS<span style={{ color: 'var(--color-red)' }}>26</span>
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
            FortiGate in Azure vWAN — Capture The Flag
          </p>
        </div>

        {/* Card */}
        <div className="card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', gap: '0', marginBottom: '1.75rem', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', padding: '3px' }}>
            <TabBtn active={mode === 'login'} to="/login" label="Sign In" />
            <TabBtn active={mode === 'register'} to="/register" label="Register" />
          </div>

          {error && <div className="alert alert-error" style={{ marginBottom: '1.25rem' }}>{error}</div>}

          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Username</label>
              <input
                className="form-input"
                type="text"
                placeholder="your_handle"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>

            {mode === 'register' && (
              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  className="form-input"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  className="form-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  style={{ paddingRight: '2.75rem' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  style={{
                    position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              className="btn btn-primary"
              type="submit"
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem', fontSize: '1rem' }}
            >
              {loading ? <span className="spinner" style={{ width: 16, height: 16 }} /> : null}
              {mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>

        <p style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
          Fortinet EMEA · Madrid · 6-11 July 2026
        </p>
      </div>
    </div>
  )
}

function TabBtn({ active, to, label }: { active: boolean; to: string; label: string }) {
  return (
    <Link
      to={to}
      style={{
        flex: 1, textAlign: 'center',
        padding: '0.5rem',
        borderRadius: '6px',
        fontFamily: 'var(--font-display)',
        fontWeight: 700,
        fontSize: '0.9rem',
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
        background: active ? 'var(--color-red)' : 'transparent',
        color: active ? 'white' : 'var(--color-text-muted)',
        textDecoration: 'none',
        transition: 'all 0.2s',
      }}
    >
      {label}
    </Link>
  )
}
