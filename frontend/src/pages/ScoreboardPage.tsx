import { useState, useEffect, useCallback } from 'react'
import { Trophy, Zap, Target, ArrowDown } from 'lucide-react'
import { scoreboardApi, type Scoreboard, type ScoreboardEntry } from '@/utils/api'
import { useScoreboardWS } from '@/hooks/useScoreboardWS'

export default function ScoreboardPage() {
  const [scoreboard, setScoreboard] = useState<Scoreboard | null>(null)
  const [flash, setFlash] = useState<number | null>(null)

  useEffect(() => {
    scoreboardApi.get().then(r => setScoreboard(r.data))
  }, [])

  const onMessage = useCallback((msg: { type: string; data: unknown }) => {
    if (msg.type === 'scoreboard_update') {
      const data = msg.data as Scoreboard
      setScoreboard(prev => {
        // Detect rank changes for animation
        if (prev) {
          const newLeader = data.entries[0]
          const oldLeader = prev.entries[0]
          if (newLeader && oldLeader && newLeader.team_id !== oldLeader.team_id) {
            setFlash(newLeader.team_id)
            setTimeout(() => setFlash(null), 2000)
          }
        }
        return data
      })
    }
  }, [])

  useScoreboardWS(onMessage)

  const statusColor = {
    pending: 'var(--color-text-muted)',
    running: 'var(--color-success)',
    paused: 'var(--color-warning)',
    finished: 'var(--color-text-muted)',
  }

  return (
    <div className="page-enter" style={{ maxWidth: 800, margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
        <Trophy size={32} color="var(--color-red)" />
        <div>
          <h2>Scoreboard</h2>
          {scoreboard && (
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem', fontSize: '0.8rem', alignItems: 'center' }}>
              <span style={{ color: statusColor[scoreboard.event_status] ?? 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
                ● {scoreboard.event_status}
              </span>
              <span className="text-dim">Live — updates automatically</span>
            </div>
          )}
        </div>
      </div>

      {!scoreboard ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
          <span className="spinner" style={{ width: 32, height: 32 }} />
        </div>
      ) : scoreboard.entries.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '4rem', color: 'var(--color-text-muted)' }}>
          <Target size={40} style={{ marginBottom: '1rem', opacity: 0.3 }} />
          <p>No scores yet. Get solving!</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {scoreboard.entries.map((entry) => (
            <ScoreRow
              key={entry.team_id}
              entry={entry}
              isFlashing={flash === entry.team_id}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ScoreRow({ entry, isFlashing }: { entry: ScoreboardEntry; isFlashing: boolean }) {
  const isTop3 = entry.rank <= 3
  const rankColors = ['#ffd700', '#c0c0c0', '#cd7f32']

  return (
    <div style={{
      background: isTop3 ? 'var(--color-surface-2)' : 'var(--color-surface)',
      border: `1px solid ${isTop3 ? 'var(--color-border-bright)' : 'var(--color-border)'}`,
      borderRadius: 'var(--radius-lg)',
      padding: '1rem 1.25rem',
      display: 'flex',
      alignItems: 'center',
      gap: '1rem',
      transition: 'all 0.3s',
      boxShadow: isFlashing ? '0 0 20px rgba(0,212,212,0.3)' : undefined,
      animation: isFlashing ? 'pulse 0.5s ease 3' : undefined,
    }}>
      {/* Rank */}
      <div style={{
        width: 40, height: 40, flexShrink: 0,
        borderRadius: '50%',
        background: isTop3 ? `rgba(${entry.rank === 1 ? '255,215,0' : entry.rank === 2 ? '192,192,192' : '205,127,50'},0.1)` : 'var(--color-surface-2)',
        border: `2px solid ${isTop3 ? rankColors[entry.rank - 1] : 'var(--color-border)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-display)',
        fontWeight: 900,
        fontSize: '1.1rem',
        color: isTop3 ? rankColors[entry.rank - 1] : 'var(--color-text-muted)',
      }}>
        {entry.rank === 1 ? <Trophy size={18} color={rankColors[0]} /> : entry.rank}
      </div>

      {/* Team name */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-text)' }}>
          {entry.team_name}
        </div>
        <div style={{ display: 'flex', gap: '1rem', marginTop: '0.2rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
          <span><Target size={11} style={{ display: 'inline', marginRight: 3 }} />{entry.solve_count} solves</span>
          {entry.hint_cost > 0 && (
            <span style={{ color: 'var(--color-warning)' }}>
              <ArrowDown size={11} style={{ display: 'inline', marginRight: 3 }} />−{entry.hint_cost} hints
            </span>
          )}
        </div>
      </div>

      {/* Score */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 900,
          fontSize: '1.75rem',
          color: isTop3 ? rankColors[entry.rank - 1] : 'var(--color-red)',
          lineHeight: 1,
        }}>
          {entry.score.toLocaleString()}
        </div>
        <div style={{ fontSize: '0.65rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>pts</div>
      </div>

      {entry.rank === 1 && (
        <Zap size={18} color="#ffd700" style={{ flexShrink: 0 }} />
      )}
    </div>
  )
}
