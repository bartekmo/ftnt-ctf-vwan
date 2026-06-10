import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, AlertTriangle, HelpCircle } from 'lucide-react'
import { infraApi, progressApi, type ProgressTeam } from '@/utils/api'
import { challenges } from '@/utils/challenges'

// Only scored challenges appear in the progress table
const SCORED = challenges.filter(c => c.scored)

// Probers that exist (have a prober file) — used to distinguish "not solved" from "not implemented"
const IMPLEMENTED_PROBERS = new Set([
  'check_nva_deployed',
  'check_nva_licensed',
  'check_nva_bgp',
  'check_spoke_peered',
  'arm_intent_routing',
  'slb_inbound',
  'fgt_fgsp',
  'overlay_template',
])

interface HubRow {
  hub: { name: string; location: string }
  team: ProgressTeam | null
}

export default function ProgressPage() {
  const [rows, setRows] = useState<HubRow[]>([])
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  useEffect(() => {
    Promise.all([
      infraApi.listHubs(),
      progressApi.progress(),
    ]).then(([hubsRes, progressRes]) => {
      const teams: ProgressTeam[] = progressRes.data
      const teamByEnvId = new Map(
        teams.filter(t => t.env_id).map(t => [t.env_id!, t])
      )

      const hubRows: HubRow[] = hubsRes.data.hubs.map((hub: { name: string; location: string }) => {
        // Hub name is e.g. "hub01" — env_id is "01"
        const envId = hub.name.replace(/^hub/, '')
        return {
          hub,
          team: teamByEnvId.get(envId) ?? null,
        }
      })

      setRows(hubRows.sort((a, b) => a.hub.name.localeCompare(b.hub.name)))
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const toggle = (name: string) => setCollapsed(prev => {
    const next = new Set(prev)
    next.has(name) ? next.delete(name) : next.add(name)
    return next
  })

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <span className="spinner" style={{ width: 32, height: 32 }} />
    </div>
  )

  return (
    <div className="page-enter" style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <h2 style={{ marginBottom: '0.25rem' }}>Progress</h2>
      <p className="text-muted" style={{ marginBottom: '2rem', fontSize: '0.9rem' }}>
        Live challenge completion status and prober warnings per hub
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {rows.map(({ hub, team }) => {
          const isCollapsed = collapsed.has(hub.name)
          return (
            <div key={hub.name} className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {/* Title bar — clickable */}
              <div
                onClick={() => toggle(hub.name)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.75rem',
                  padding: '0.85rem 1.25rem', cursor: 'pointer',
                  background: 'var(--color-surface-2)',
                  borderBottom: isCollapsed ? 'none' : '1px solid var(--color-border)',
                  userSelect: 'none',
                }}
              >
                {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem' }}>
                  {hub.name}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  {hub.location}
                </span>
                <span style={{ marginLeft: 'auto', fontSize: '0.85rem', color: team ? 'var(--color-teal)' : 'var(--color-text-dim)' }}>
                  {team ? team.team_name : 'unassigned'}
                </span>
                {team && (
                  <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--color-red)', fontSize: '1.1rem' }}>
                    {team.score} pts
                  </span>
                )}
              </div>

              {/* Expanded content */}
              {!isCollapsed && (
                <div style={{ padding: '1rem 1.25rem' }}>
                  {!team ? (
                    <p className="text-muted" style={{ fontSize: '0.9rem' }}>No team assigned to this hub.</p>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                          {['Challenge', 'Status', 'Points', 'Warnings'].map(h => (
                            <th key={h} style={{
                              padding: '0.4rem 0.6rem', textAlign: 'left',
                              fontFamily: 'var(--font-display)', fontWeight: 700,
                              fontSize: '0.72rem', textTransform: 'uppercase',
                              letterSpacing: '0.08em', color: 'var(--color-text-muted)',
                            }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {SCORED.map(c => {
                          const solve = team.solves[c.id]
                          const prober = c.prober
                          const implemented = prober ? IMPLEMENTED_PROBERS.has(prober) : false
                          const allWarnings = prober ? (team.warnings[prober] ?? []) : []

                          return (
                            <tr key={c.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                              <td style={{ padding: '0.5rem 0.6rem', color: 'var(--color-text)' }}>
                                {c.title}
                              </td>
                              <td style={{ padding: '0.5rem 0.6rem' }}>
                                {solve ? (
                                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: '#4ade80' }}>
                                    <CheckCircle2 size={13} /> solved
                                  </span>
                                ) : implemented ? (
                                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: 'var(--color-text-muted)' }}>
                                    <XCircle size={13} /> not solved
                                  </span>
                                ) : (
                                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: 'var(--color-text-dim)' }}>
                                    <HelpCircle size={13} /> not implemented
                                  </span>
                                )}
                              </td>
                              <td style={{ padding: '0.5rem 0.6rem', fontFamily: 'var(--font-mono)', color: solve ? 'var(--color-red)' : 'var(--color-text-dim)' }}>
                                {solve ? `+${solve.points}` : '—'}
                              </td>
                              <td style={{ padding: '0.5rem 0.6rem' }}>
                                {allWarnings.length > 0 ? (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                    {allWarnings.map(w => (
                                      <span key={w.key} style={{
                                        display: 'inline-flex', alignItems: 'flex-start', gap: '0.3rem',
                                        color: 'var(--color-warning)', fontSize: '0.8rem',
                                      }}>
                                        <AlertTriangle size={12} style={{ flexShrink: 0, marginTop: 2 }} />
                                        {w.message}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-dim" style={{ fontSize: '0.8rem' }}>—</span>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
