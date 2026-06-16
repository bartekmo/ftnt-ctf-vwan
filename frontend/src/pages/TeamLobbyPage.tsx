import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Plus, LogIn } from 'lucide-react'
import { teamsApi, type Team } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/utils/api'

export default function TeamLobbyPage() {
  const { user, setAuth, token } = useAuthStore()
  const navigate = useNavigate()
  const [teams, setTeams] = useState<Team[]>([])
  const [tab, setTab] = useState<'create' | 'join'>('join')
  const [teamName, setTeamName] = useState('')
  const [joinCode, setJoinCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (user?.team_id) navigate('/challenges')
    teamsApi.list().then(r => setTeams(r.data))
  }, [user, navigate])

  const refresh = async () => {
    const me = await authApi.me()
    if (token) setAuth(me.data, token)
    if (me.data.team_id) navigate('/challenges')
  }

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await teamsApi.create(teamName)
      await refresh()
    } catch (err: unknown) {
      const e2 = err as { response?: { data?: { detail?: string } } }
      setError(e2.response?.data?.detail ?? 'Could not create team')
    } finally { setLoading(false) }
  }

  const join = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await teamsApi.join(joinCode)
      await refresh()
    } catch (err: unknown) {
      const e2 = err as { response?: { data?: { detail?: string } } }
      setError(e2.response?.data?.detail ?? 'Could not join team')
    } finally { setLoading(false) }
  }

  return (
    <div className="page-enter" style={{ maxWidth: 600, margin: '4rem auto', padding: '0 1.5rem' }}>
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <Users size={40} color="var(--color-teal)" style={{ marginBottom: '1rem' }} />
        <h2>Join a Team</h2>
        <p className="text-muted" style={{ marginTop: '0.5rem' }}>
          You need to be on a team to participate.
        </p>
      </div>

      {/* Existing teams */}
      {teams.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}>
            Existing Teams ({teams.length})
          </div>
          <div style={{ display: 'grid', gap: '0.5rem', maxHeight: 220, overflowY: 'auto' }}>
            {teams.map(t => (
              <div key={t.id} style={{
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{ fontWeight: 600 }}>{t.name}</span>
                <span className="badge badge-teal">
                  {t.member_count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="card" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', gap: '0', marginBottom: '1.5rem', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-md)', padding: '3px' }}>
          {(['join', 'create'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, padding: '0.5rem',
              background: tab === t ? 'var(--color-teal-dim)' : 'transparent',
              color: tab === t ? 'white' : 'var(--color-text-muted)',
              border: 'none', borderRadius: '6px',
              fontFamily: 'var(--font-display)', fontWeight: 700,
              fontSize: '0.9rem', letterSpacing: '0.05em', textTransform: 'uppercase',
              cursor: 'pointer', transition: 'all 0.2s',
            }}>
              {t === 'join' ? <><LogIn size={14} style={{ display: 'inline', marginRight: 6 }} />Join</> : <><Plus size={14} style={{ display: 'inline', marginRight: 6 }} />Create</>}
            </button>
          ))}
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

        {tab === 'join' ? (
          <form onSubmit={join} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Team Join Code</label>
              <input
                className="form-input"
                placeholder="Enter 8-character code"
                value={joinCode}
                onChange={e => setJoinCode(e.target.value.toUpperCase())}
                required
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', fontSize: '1.1rem' }}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>
                Get the code from your teammate or trainer
              </span>
            </div>
            <button className="btn btn-secondary" type="submit" disabled={loading} style={{ justifyContent: 'center' }}>
              {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : null}
              Join Team
            </button>
          </form>
        ) : (
          <form onSubmit={create} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Team Name</label>
              <input
                className="form-input"
                placeholder="Team Awesome"
                value={teamName}
                onChange={e => setTeamName(e.target.value)}
                required
              />
            </div>
            <button className="btn btn-primary" type="submit" disabled={loading} style={{ justifyContent: 'center' }}>
              {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : null}
              Create Team
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
