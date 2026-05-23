import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, CheckCircle2, AlertTriangle } from 'lucide-react'
import { challengesApi, type Challenge, type Hint } from '@/utils/api'

export default function ChallengeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [hints, setHints] = useState<Hint[]>([])
  const [unlocking, setUnlocking] = useState<number | null>(null)
  const [confirmHint, setConfirmHint] = useState<Hint | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    Promise.all([
      challengesApi.get(Number(id)),
      challengesApi.hints(Number(id)),
    ]).then(([c, h]) => {
      setChallenge(c.data)
      setHints(h.data)
      setLoading(false)
    })
  }, [id])

  const unlockHint = async (hint: Hint) => {
    if (hint.is_purchased) return
    setConfirmHint(hint)
  }

  const confirmUnlock = async () => {
    if (!confirmHint || !id) return
    setUnlocking(confirmHint.id)
    setConfirmHint(null)
    try {
      const res = await challengesApi.unlockHint(Number(id), confirmHint.id)
      setHints(prev => prev.map(h => h.id === confirmHint.id ? res.data : h))
    } finally {
      setUnlocking(null)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <span className="spinner" style={{ width: 32, height: 32 }} />
    </div>
  )

  if (!challenge) return <div style={{ padding: '4rem', textAlign: 'center' }}>Challenge not found</div>

  return (
    <div className="page-enter" style={{ maxWidth: 780, margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Back */}
      <button onClick={() => navigate('/challenges')} className="btn btn-ghost" style={{ marginBottom: '1.5rem', fontSize: '0.85rem' }}>
        <ArrowLeft size={15} /> Back to Challenges
      </button>

      {/* Header */}
      <div className="card" style={{ marginBottom: '1.25rem', position: 'relative', overflow: 'hidden' }}>
        {challenge.is_solved_by_team && <div className="solved-overlay" />}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="badge badge-teal">{challenge.category}</span>
              {challenge.is_solved_by_team && (
                <span className="badge badge-green"><CheckCircle2 size={11} /> Solved</span>
              )}
            </div>
            <h2 style={{ marginBottom: '0.25rem' }}>{challenge.title}</h2>
            <p className="text-muted" style={{ fontSize: '0.85rem' }}>
              {challenge.solve_count} team{challenge.solve_count !== 1 ? 's' : ''} solved
            </p>
          </div>
          <div style={{ textAlign: 'center', flexShrink: 0 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.5rem', fontWeight: 900, color: 'var(--color-red)', lineHeight: 1 }}>
              {challenge.base_points}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>base points</div>
          </div>
        </div>
      </div>

      {/* Description */}
      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <h3 style={{ marginBottom: '1rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
          Instructions
        </h3>
        <div style={{
          lineHeight: 1.75,
          color: 'var(--color-text)',
          whiteSpace: 'pre-wrap',
          fontFamily: 'var(--font-body)',
        }}>
          {challenge.description}
        </div>
      </div>

      {/* Hints */}
      {hints.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
            Hints ({hints.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {hints.map((hint, i) => (
              <HintCard
                key={hint.id}
                hint={hint}
                index={i}
                onUnlock={() => unlockHint(hint)}
                isUnlocking={unlocking === hint.id}
              />
            ))}
          </div>
        </div>
      )}

      {/* Confirm modal */}
      {confirmHint && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, padding: '1rem',
        }}>
          <div className="card" style={{ maxWidth: 380, width: '100%', textAlign: 'center' }}>
            <AlertTriangle size={36} color="var(--color-warning)" style={{ marginBottom: '1rem' }} />
            <h3 style={{ marginBottom: '0.5rem' }}>Use Hint?</h3>
            <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.9rem' }}>
              This hint costs <strong style={{ color: 'var(--color-red)' }}>{confirmHint.points_cost} points</strong>. The deduction is immediate and permanent.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button className="btn btn-ghost" onClick={() => setConfirmHint(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={confirmUnlock}>Use Hint (−{confirmHint.points_cost} pts)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function HintCard({ hint, index, onUnlock, isUnlocking }: {
  hint: Hint
  index: number
  onUnlock: () => void
  isUnlocking: boolean
}) {
  return (
    <div style={{
      background: 'var(--color-surface-2)',
      border: `1px solid ${hint.is_purchased ? 'rgba(0,212,212,0.25)' : 'var(--color-border)'}`,
      borderRadius: 'var(--radius-md)',
      padding: '1rem',
      display: 'flex',
      gap: '1rem',
      alignItems: hint.is_purchased ? 'flex-start' : 'center',
    }}>
      <div style={{
        flexShrink: 0,
        width: 28, height: 28,
        background: hint.is_purchased ? 'rgba(0,212,212,0.1)' : 'var(--color-surface)',
        border: `1px solid ${hint.is_purchased ? 'rgba(0,212,212,0.3)' : 'var(--color-border)'}`,
        borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
        color: hint.is_purchased ? 'var(--color-teal)' : 'var(--color-text-muted)',
      }}>
        {hint.is_purchased ? <Eye size={12} /> : index + 1}
      </div>

      <div style={{ flex: 1 }}>
        {hint.is_purchased ? (
          <p style={{ color: 'var(--color-text)', lineHeight: 1.6 }}>{hint.content}</p>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <span className="text-muted" style={{ fontSize: '0.9rem' }}>Hint #{index + 1} — locked</span>
            <button
              className="btn btn-ghost"
              onClick={onUnlock}
              disabled={isUnlocking}
              style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
            >
              {isUnlocking ? <span className="spinner" style={{ width: 12, height: 12 }} /> : null}
              Unlock (−{hint.points_cost} pts)
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
