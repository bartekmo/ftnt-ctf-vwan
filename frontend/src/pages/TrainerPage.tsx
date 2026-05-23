import { useState, useEffect } from 'react'
import { Play, Pause, Square, RotateCcw, Users, Eye, BookOpen, Shuffle } from 'lucide-react'
import { scoreboardApi, challengesApi, usersApi, teamsApi, type CTFEvent, type HintUse, type Team } from '@/utils/api'
import type { User } from '@/utils/api'

type Tab = 'event' | 'teams' | 'hints'

export default function TrainerPage() {
  const [tab, setTab] = useState<Tab>('event')
  const [event, setEvent] = useState<CTFEvent | null>(null)
  const [hintUses, setHintUses] = useState<HintUse[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    scoreboardApi.getEvent().then(r => setEvent(r.data))
    challengesApi.allHintUses().then(r => setHintUses(r.data))
    teamsApi.list().then(r => setTeams(r.data))
    usersApi.list().then(r => setUsers(r.data))
  }, [])

  const setStatus = async (status: CTFEvent['status']) => {
    setLoading(true)
    try {
      const r = await scoreboardApi.updateEvent({ status })
      setEvent(r.data)
      setMsg(`Event status → ${status}`)
    } finally { setLoading(false) }
  }

  const reset = async () => {
    if (!confirm('Reset all scores and solves? This cannot be undone.')) return
    setLoading(true)
    try {
      await scoreboardApi.resetEvent()
      setMsg('Event reset.')
      setEvent(prev => prev ? { ...prev, status: 'pending', started_at: null, finished_at: null } : prev)
    } finally { setLoading(false) }
  }

  const shuffle = async () => {
    if (!confirm('Randomly reassign all attendees to teams?')) return
    const r = await teamsApi.shuffle()
    setMsg(`Shuffled ${r.data.reassigned} attendees`)
    const [tu, uu] = await Promise.all([teamsApi.list(), usersApi.list()])
    setTeams(tu.data); setUsers(uu.data)
  }

  const moveUser = async (userId: number, teamId: number | null) => {
    await teamsApi.moveUser(userId, teamId)
    const [tu, uu] = await Promise.all([teamsApi.list(), usersApi.list()])
    setTeams(tu.data); setUsers(uu.data)
  }

  return (
    <div className="page-enter" style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <h2 style={{ marginBottom: '0.25rem' }}>Trainer Panel</h2>
      <p className="text-muted" style={{ marginBottom: '2rem', fontSize: '0.9rem' }}>Manage the CTF event, teams, and monitor hint usage</p>

      {msg && <div className="alert alert-success" style={{ marginBottom: '1.5rem' }} onClick={() => setMsg('')}>{msg} ✕</div>}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0' }}>
        {([
          { key: 'event', label: 'Event Control', icon: <Play size={15} /> },
          { key: 'teams', label: 'Teams & Users', icon: <Users size={15} /> },
          { key: 'hints', label: 'Hint Usage', icon: <Eye size={15} /> },
        ] as { key: Tab; label: string; icon: React.ReactNode }[]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            padding: '0.6rem 1rem',
            background: 'none', border: 'none',
            borderBottom: tab === t.key ? '2px solid var(--color-teal)' : '2px solid transparent',
            color: tab === t.key ? 'var(--color-teal)' : 'var(--color-text-muted)',
            fontFamily: 'var(--font-display)', fontWeight: 600,
            fontSize: '0.9rem', letterSpacing: '0.04em', textTransform: 'uppercase',
            cursor: 'pointer', transition: 'all 0.15s',
            marginBottom: '-1px',
          }}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* Event Control */}
      {tab === 'event' && event && (
        <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {/* Status card */}
          <div className="card">
            <h3 style={{ marginBottom: '1.25rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
              Event Status
            </h3>
            <div style={{ marginBottom: '1.25rem' }}>
              <span className={`badge ${event.status === 'running' ? 'badge-green' : event.status === 'paused' ? 'badge-red' : 'badge-gray'}`} style={{ fontSize: '0.85rem', padding: '0.3rem 0.8rem' }}>
                {event.status.toUpperCase()}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {event.status !== 'running' && (
                <button className="btn btn-primary" onClick={() => setStatus('running')} disabled={loading} style={{ justifyContent: 'center' }}>
                  <Play size={15} /> Start CTF
                </button>
              )}
              {event.status === 'running' && (
                <button className="btn btn-ghost" onClick={() => setStatus('paused')} disabled={loading} style={{ justifyContent: 'center' }}>
                  <Pause size={15} /> Pause
                </button>
              )}
              {event.status === 'paused' && (
                <button className="btn btn-secondary" onClick={() => setStatus('running')} disabled={loading} style={{ justifyContent: 'center' }}>
                  <Play size={15} /> Resume
                </button>
              )}
              {(event.status === 'running' || event.status === 'paused') && (
                <button className="btn btn-ghost" onClick={() => setStatus('finished')} disabled={loading} style={{ justifyContent: 'center' }}>
                  <Square size={15} /> Finish
                </button>
              )}
              <button className="btn btn-danger" onClick={reset} disabled={loading} style={{ justifyContent: 'center' }}>
                <RotateCcw size={15} /> Reset Scores
              </button>
            </div>
          </div>

          {/* Stats card */}
          <div className="card">
            <h3 style={{ marginBottom: '1.25rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
              Event Stats
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <StatRow label="Teams" value={String(teams.length)} />
              <StatRow label="Attendees" value={String(users.filter(u => u.role === 'attendee').length)} />
              <StatRow label="Hints used" value={String(hintUses.length)} />
              {event.started_at && (
                <StatRow label="Started" value={new Date(event.started_at).toLocaleTimeString()} />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Teams & Users */}
      {tab === 'teams' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
            <button className="btn btn-secondary" onClick={shuffle} style={{ fontSize: '0.85rem' }}>
              <Shuffle size={14} /> Random Shuffle
            </button>
          </div>
          <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
            {teams.map(team => {
              const members = users.filter(u => u.team_id === team.id)
              const unassigned = users.filter(u => u.role === 'attendee' && !u.team_id)
              return (
                <div key={team.id} className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div>
                      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem' }}>{team.name}</div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-teal)', marginTop: '0.2rem' }}>{team.join_code}</div>
                    </div>
                    <span className="badge badge-teal">{members.length}/2</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.75rem' }}>
                    {members.map(u => (
                      <div key={u.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.4rem 0.6rem', background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)' }}>
                        <span style={{ fontSize: '0.9rem' }}>{u.username}</span>
                        <button onClick={() => moveUser(u.id, null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: '0.75rem' }}>remove</button>
                      </div>
                    ))}
                    {members.length === 0 && <p style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)' }}>No members</p>}
                  </div>
                  {members.length < 2 && unassigned.length > 0 && (
                    <select
                      defaultValue=""
                      onChange={e => { if (e.target.value) moveUser(Number(e.target.value), team.id); e.target.value = '' }}
                      className="form-input"
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
                    >
                      <option value="">Add attendee…</option>
                      {unassigned.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
                    </select>
                  )}
                </div>
              )
            })}
          </div>

          {/* Unassigned users */}
          {users.filter(u => u.role === 'attendee' && !u.team_id).length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <h3 style={{ fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: '0.75rem' }}>Unassigned</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {users.filter(u => u.role === 'attendee' && !u.team_id).map(u => (
                  <span key={u.id} className="badge badge-gray">{u.username}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Hint Usage */}
      {tab === 'hints' && (
        <div>
          <div style={{ marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
            {hintUses.length} total hint unlock{hintUses.length !== 1 ? 's' : ''}
          </div>
          {hintUses.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--color-text-muted)' }}>
              <BookOpen size={36} style={{ marginBottom: '0.75rem', opacity: 0.3 }} />
              <p>No hints used yet</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                    {['Team', 'Challenge', 'Cost', 'Time'].map(h => (
                      <th key={h} style={{ padding: '0.6rem 0.75rem', textAlign: 'left', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {hintUses.map((hu, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td style={{ padding: '0.65rem 0.75rem', fontWeight: 600 }}>{hu.team_name}</td>
                      <td style={{ padding: '0.65rem 0.75rem', color: 'var(--color-text-muted)' }}>{hu.challenge_title}</td>
                      <td style={{ padding: '0.65rem 0.75rem', color: 'var(--color-warning)', fontFamily: 'var(--font-mono)' }}>−{hu.points_cost}</td>
                      <td style={{ padding: '0.65rem 0.75rem', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{new Date(hu.used_at).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--color-border)' }}>
      <span className="text-muted" style={{ fontSize: '0.85rem' }}>{label}</span>
      <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem' }}>{value}</span>
    </div>
  )
}
