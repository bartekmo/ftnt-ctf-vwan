import { useState, useEffect } from 'react'
import { Play, Pause, Square, RotateCcw, Users, BookOpen, Shuffle, Key, AlertTriangle, UserCheck } from 'lucide-react'
import { scoreboardApi, usersApi, teamsApi, type CTFEvent, type Team, type TapPreview, type TapResult } from '@/utils/api'
import type { User } from '@/utils/api'

type Tab = 'event' | 'teams' | 'users'

export default function TrainerPage() {
  const [tab, setTab]           = useState<Tab>('event')
  const [event, setEvent]       = useState<CTFEvent | null>(null)
  const [teams, setTeams]       = useState<Team[]>([])
  const [users, setUsers]       = useState<User[]>([])
  const [loading, setLoading]   = useState(false)
  const [tapPreview, setTapPreview] = useState<TapPreview | null>(null)
  const [tapResult, setTapResult]   = useState<TapResult | null>(null)
  const [tapLoading, setTapLoading] = useState(false)
  const [msg, setMsg]           = useState('')

  const refresh = async () => {
    const [te, tu, uu] = await Promise.all([
      scoreboardApi.getEvent(), teamsApi.list(), usersApi.list()
    ])
    setEvent(te.data); setTeams(tu.data); setUsers(uu.data)
  }

  useEffect(() => { refresh() }, [])

  const setStatus = async (status: CTFEvent['status']) => {
    setLoading(true)
    try {
      const r = await scoreboardApi.updateEvent({ status })
      setEvent(r.data); setMsg(`Event status → ${status}`)
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

  const previewTaps = async () => {
    setTapLoading(true); setTapPreview(null); setTapResult(null)
    try { const r = await usersApi.tapPreview(); setTapPreview(r.data) }
    catch { setMsg('Failed to fetch TAP preview.') }
    finally { setTapLoading(false) }
  }

  const confirmTaps = async () => {
    if (!tapPreview) return
    if (!confirm(`Create new TAPs for ${tapPreview.count} student account(s)?\nEach TAP is valid for ${tapPreview.tap_lifetime_minutes / 60}h.\nExisting TAPs will be replaced.`)) { setTapPreview(null); return }
    setTapLoading(true); setTapPreview(null)
    try { const r = await usersApi.recreateTaps(); setTapResult(r.data); setMsg(`TAPs created: ${r.data.ok} ok, ${r.data.errors} errors`) }
    catch { setMsg('TAP creation failed.') }
    finally { setTapLoading(false) }
  }

  const resetDb = async () => {
    if (!confirm('WIPE ENTIRE DATABASE? Deletes ALL users, teams and scores.')) return
    if (!confirm('Are you absolutely sure?')) return
    setLoading(true)
    try { await usersApi.resetDb(); setMsg('Database wiped. Reload the page and re-seed the trainer account.') }
    catch { setMsg('Database reset failed.') }
    finally { setLoading(false) }
  }

  const shuffle = async () => {
    if (!confirm('Randomly reassign all attendees to teams?')) return
    const r = await teamsApi.shuffle()
    setMsg(`Shuffled ${r.data.reassigned} attendees`)
    await refresh()
  }

  const moveUser = async (userId: number, teamId: number | null) => {
    await teamsApi.moveUser(userId, teamId); await refresh()
  }

  const changeEnvId = async (team: Team) => {
    const raw = prompt(`New environment index for team "${team.name}" (e.g. 03):\nCurrent: ${team.env_id ?? 'unassigned'}`)
    if (!raw) return
    const envId = raw.trim().padStart(2, '0')
    if (!/^\d{2}$/.test(envId)) { setMsg('Invalid index — must be 2 digits'); return }
    if (!confirm(`Change "${team.name}" from hub${team.env_id ?? '??'} to hub${envId}?`)) return
    const resetSolves = confirm(`Reset all solves, hints and warnings for "${team.name}"?\n(Recommended when changing environment)`)
    try {
      await teamsApi.setEnvId(team.id, envId)
      if (resetSolves) await teamsApi.resetSolves(team.id)
      setMsg(`Team "${team.name}" → hub${envId}${resetSolves ? ' (solves reset)' : ''}`)
      await refresh()
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Failed to change env_id')
    }
  }

  const toggleRole = async (user: User) => {
    const newRole = user.role === 'trainer' ? 'attendee' : 'trainer'
    if (!confirm(`Change ${user.username} role to ${newRole}?`)) return
    await usersApi.setRole(user.id, newRole)
    await refresh()
  }

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'event', label: 'Event Control', icon: <Play size={15} /> },
    { key: 'teams', label: 'Teams',         icon: <BookOpen size={15} /> },
    { key: 'users', label: 'Users',         icon: <UserCheck size={15} /> },
  ]

  return (
    <div className="page-enter" style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <h2 style={{ marginBottom: '0.25rem' }}>Trainer Panel</h2>
      <p className="text-muted" style={{ marginBottom: '2rem', fontSize: '0.9rem' }}>Manage the CTF event, teams and users</p>

      {msg && <div className="alert alert-success" style={{ marginBottom: '1.5rem', cursor: 'pointer' }} onClick={() => setMsg('')}>{msg} ✕</div>}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', borderBottom: '1px solid var(--color-border)' }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            padding: '0.6rem 1rem', background: 'none', border: 'none',
            borderBottom: tab === t.key ? '2px solid var(--color-teal)' : '2px solid transparent',
            color: tab === t.key ? 'var(--color-teal)' : 'var(--color-text-muted)',
            fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.9rem',
            letterSpacing: '0.04em', textTransform: 'uppercase', cursor: 'pointer',
            marginBottom: '-1px', transition: 'all 0.15s',
          }}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* ── Event Control ──────────────────────────────────────────────── */}
      {tab === 'event' && event && (
        <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          <div className="card">
            <h3 style={{ marginBottom: '1.25rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>Event Status</h3>
            <div style={{ marginBottom: '1.25rem' }}>
              <span className={`badge ${event.status === 'running' ? 'badge-green' : event.status === 'paused' ? 'badge-red' : 'badge-gray'}`} style={{ fontSize: '0.85rem', padding: '0.3rem 0.8rem' }}>
                {event.status.toUpperCase()}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {event.status !== 'running' && <button className="btn btn-primary" onClick={() => setStatus('running')} disabled={loading} style={{ justifyContent: 'center' }}><Play size={15} /> Start CTF</button>}
              {event.status === 'running' && <button className="btn btn-ghost" onClick={() => setStatus('paused')} disabled={loading} style={{ justifyContent: 'center' }}><Pause size={15} /> Pause</button>}
              {event.status === 'paused'  && <button className="btn btn-secondary" onClick={() => setStatus('running')} disabled={loading} style={{ justifyContent: 'center' }}><Play size={15} /> Resume</button>}
              {(event.status === 'running' || event.status === 'paused') && <button className="btn btn-ghost" onClick={() => setStatus('finished')} disabled={loading} style={{ justifyContent: 'center' }}><Square size={15} /> Finish</button>}
              <button className="btn btn-danger" onClick={reset} disabled={loading} style={{ justifyContent: 'center' }}><RotateCcw size={15} /> Reset Scores</button>
              <div className="divider" style={{ margin: '0.5rem 0' }} />
              <button className="btn btn-danger" onClick={resetDb} disabled={loading} style={{ justifyContent: 'center', opacity: 0.8 }}><RotateCcw size={15} /> Reset Database</button>
              <div className="divider" style={{ margin: '1rem 0 0.5rem' }} />
              <div style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '0.5rem' }}>Temporary Access Passes</div>
              {event.status === 'running' && (
                <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 'var(--radius-md)', padding: '0.6rem 0.75rem', marginBottom: '0.5rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                  <AlertTriangle size={14} color="var(--color-warning)" style={{ flexShrink: 0, marginTop: 2 }} />
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-warning)' }}>Verify TAPs are valid before attendees sign in.</span>
                </div>
              )}
              {!tapPreview ? (
                <button className="btn btn-secondary" onClick={previewTaps} disabled={tapLoading} style={{ justifyContent: 'center' }}><Key size={15} /> {tapLoading ? 'Loading…' : 'Recreate TAPs'}</button>
              ) : (
                <div style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '0.75rem' }}>
                  <p style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Found <strong>{tapPreview.count}</strong> account(s). TAP valid for <strong>{tapPreview.tap_lifetime_minutes / 60}h</strong>.</p>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn btn-secondary" onClick={confirmTaps} disabled={tapLoading} style={{ flex: 1, justifyContent: 'center' }}><Key size={14} /> Confirm</button>
                    <button className="btn btn-ghost" onClick={() => setTapPreview(null)} style={{ flex: 1, justifyContent: 'center' }}>Cancel</button>
                  </div>
                </div>
              )}
              {tapResult && <div style={{ fontSize: '0.8rem', color: tapResult.errors > 0 ? 'var(--color-warning)' : 'var(--color-success)', marginTop: '0.25rem' }}>{tapResult.ok} TAP(s) created{tapResult.errors > 0 ? `, ${tapResult.errors} error(s)` : ''}</div>}
            </div>
          </div>
          <div className="card">
            <h3 style={{ marginBottom: '1.25rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>Event Stats</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <StatRow label="Teams"     value={String(teams.length)} />
              <StatRow label="Attendees" value={String(users.filter(u => u.role === 'attendee').length)} />
              {event.started_at && <StatRow label="Started" value={new Date(event.started_at).toLocaleTimeString()} />}
            </div>
          </div>
        </div>
      )}

      {/* ── Teams ──────────────────────────────────────────────────────── */}
      {tab === 'teams' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
            <button className="btn btn-secondary" onClick={shuffle} style={{ fontSize: '0.85rem' }}><Shuffle size={14} /> Random Shuffle</button>
          </div>
          <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
            {teams.map(team => {
              const members    = users.filter(u => u.team_id === team.id)
              const unassigned = users.filter(u => u.role === 'attendee' && !u.team_id)
              return (
                <div key={team.id} className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                    <div>
                      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem' }}>{team.name}</div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-teal)', marginTop: '0.2rem' }}>{team.join_code}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {team.hub_name ? (
                          <>
                            <span style={{ color: 'var(--color-text-dim)' }}>hub:</span>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-teal)' }}>{team.hub_name}</span>
                            <button onClick={() => changeEnvId(team)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', fontSize: '0.7rem', padding: '0 0.2rem' }}>✎</button>
                          </>
                        ) : (
                          <button onClick={() => changeEnvId(team)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-warning)', fontSize: '0.75rem' }}>assign hub…</button>
                        )}
                      </div>
                    </div>
                    <span className="badge badge-teal">{members.length}</span>
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
                  {unassigned.length > 0 && (
                    <select defaultValue="" onChange={e => { if (e.target.value) { moveUser(Number(e.target.value), team.id); e.currentTarget.value = '' } }} className="form-input" style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}>
                      <option value="">Add attendee…</option>
                      {unassigned.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
                    </select>
                  )}
                </div>
              )
            })}
          </div>
          {users.filter(u => u.role === 'attendee' && !u.team_id).length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <h3 style={{ fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: '0.75rem' }}>Unassigned</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {users.filter(u => u.role === 'attendee' && !u.team_id).map(u => <span key={u.id} className="badge badge-gray">{u.username}</span>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Users ──────────────────────────────────────────────────────── */}
      {tab === 'users' && (
        <div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Username', 'Email', 'Team', 'Hub', 'Role'].map(h => (
                  <th key={h} style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const team = teams.find(t => t.id === u.team_id)
                return (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>{u.username}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{u.email}</td>
                    <td style={{ padding: '0.5rem 0.75rem' }}>
                      <select
                        value={u.team_id ?? ''}
                        onChange={e => moveUser(u.id, e.target.value ? Number(e.target.value) : null)}
                        style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', padding: '0.2rem 0.4rem', fontSize: '0.8rem', cursor: 'pointer' }}
                      >
                        <option value="">— none —</option>
                        {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--color-teal)' }}>
                      {team?.hub_name ?? '—'}
                    </td>
                    <td style={{ padding: '0.5rem 0.75rem' }}>
                      <button
                        onClick={() => toggleRole(u)}
                        style={{ background: 'none', border: '1px solid', borderColor: u.role === 'trainer' ? 'var(--color-red)' : 'var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', color: u.role === 'trainer' ? 'var(--color-red)' : 'var(--color-text-muted)', padding: '0.15rem 0.5rem', fontSize: '0.75rem', fontFamily: 'var(--font-display)', fontWeight: 600 }}
                      >
                        {u.role}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
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
