import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, ChevronRight,
  Eye, AlertTriangle, BookOpen, ExternalLink,
} from 'lucide-react'
import { getChallengeById, challenges } from '@/utils/challenges'
import { ChallengesMDXProvider } from '@/components/challenges/MDXProvider'
import { challengesApi, type HintUnlock } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

export default function ChallengeDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const challenge = id ? getChallengeById(id) : undefined
  const allVisible = challenges.filter(c => c.visible || user?.role === 'trainer')
  const currentIdx = allVisible.findIndex(c => c.id === id)
  const prev = currentIdx > 0 ? allVisible[currentIdx - 1] : null
  const next = currentIdx < allVisible.length - 1 ? allVisible[currentIdx + 1] : null

  // Slug-based hint unlock state — no DB challenge lookup needed
  const [unlockedKeys, setUnlockedKeys] = useState<Set<string>>(new Set())
  const [unlocking, setUnlocking] = useState<number | null>(null)
  const [confirmHint, setConfirmHint] = useState<{ index: number; cost: number; text: string } | null>(null)

  useEffect(() => {
    if (!challenge || !user?.team_id) return
    setUnlockedKeys(new Set())
    challengesApi.hintUnlocks(challenge.id).then(r => {
      setUnlockedKeys(new Set(r.data.map((u: HintUnlock) => u.hint_key)))
    }).catch(() => {})
  }, [challenge?.id, user?.team_id])

  const unlockHint = async (hintIdx: number) => {
    if (!challenge?.hints?.[hintIdx]) return
    const hint = challenge.hints[hintIdx]
    setConfirmHint({ index: hintIdx, cost: hint.cost, text: hint.text })
  }

  const confirmUnlock = async () => {
    if (!confirmHint || !challenge) return
    setUnlocking(confirmHint.index)
    setConfirmHint(null)
    try {
      await challengesApi.unlockHint(challenge.id, confirmHint.index, confirmHint.cost)
      setUnlockedKeys(prev => new Set([...prev, `${challenge.id}:${confirmHint.index}`]))
    } finally {
      setUnlocking(null)
    }
  }

  if (!challenge) return (
    <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
      Challenge not found
    </div>
  )

  const { Component } = challenge

  return (
    <div className="page-enter" style={{ display: 'flex', maxWidth: 1200, margin: '0 auto', padding: '2rem 1.5rem', gap: '2rem', alignItems: 'flex-start' }}>

      {/* ── Sidebar ── */}
      <aside style={{
        width: 220, flexShrink: 0, position: 'sticky', top: 80,
        display: 'flex', flexDirection: 'column', gap: '0.35rem',
      }}>
        <div style={{ fontSize: '0.7rem', fontFamily: 'var(--font-display)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-dim)', marginBottom: '0.5rem' }}>
          Challenges
        </div>
        {allVisible.map((c, i) => {
          const active = c.id === id
          return (
            <Link
              key={c.id}
              to={`/challenges/${c.id}`}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.45rem 0.6rem',
                borderRadius: 'var(--radius-md)',
                background: active ? 'rgba(0,212,212,0.1)' : 'transparent',
                border: active ? '1px solid rgba(0,212,212,0.25)' : '1px solid transparent',
                textDecoration: 'none',
                color: active ? 'var(--color-teal)' : 'var(--color-text-muted)',
                fontSize: '0.82rem',
                lineHeight: 1.3,
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', flexShrink: 0, opacity: 0.6 }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              {c.title}
              {active && <ChevronRight size={11} style={{ marginLeft: 'auto', flexShrink: 0 }} />}
            </Link>
          )
        })}
      </aside>

      {/* ── Main content ── */}
      <div style={{ flex: 1, minWidth: 0 }}>

        {/* Header card */}
        <div className="card" style={{ marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <span className={`badge ${
                  challenge.category === 'vpn' || challenge.category === 'security' ? 'badge-red' : 'badge-teal'
                }`}>{challenge.category}</span>
                {!challenge.scored && (
                  <span className="badge badge-gray"><BookOpen size={10} /> Informational</span>
                )}
              </div>
              <h2 style={{ marginBottom: '0.15rem' }}>{challenge.title}</h2>
            </div>
            {challenge.scored && challenge.points > 0 && (
              <div style={{ textAlign: 'center', flexShrink: 0 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: '2.5rem', fontWeight: 900, color: 'var(--color-red)', lineHeight: 1 }}>
                  {challenge.points}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>base points</div>
              </div>
            )}
          </div>
        </div>

        {/* MDX content */}
        <div className="card" style={{ marginBottom: '1.25rem' }}>
          <ChallengesMDXProvider>
            <Component />
          </ChallengesMDXProvider>
        </div>

        {/* Hints */}
        {challenge.hints && challenge.hints.length > 0 && (
          <div className="card" style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
              Hints ({challenge.hints.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {challenge.hints.map((hint, i) => {
                const hintKey = `${challenge.id}:${i}`
                const purchased = unlockedKeys.has(hintKey)
                return (
                  <div key={i} style={{
                    background: 'var(--color-surface-2)',
                    border: `1px solid ${purchased ? 'rgba(0,212,212,0.25)' : 'var(--color-border)'}`,
                    borderRadius: 'var(--radius-md)',
                    padding: '1rem',
                    display: 'flex', gap: '1rem',
                    alignItems: purchased ? 'flex-start' : 'center',
                  }}>
                    <div style={{
                      flexShrink: 0, width: 28, height: 28,
                      background: purchased ? 'rgba(0,212,212,0.1)' : 'var(--color-surface)',
                      border: `1px solid ${purchased ? 'rgba(0,212,212,0.3)' : 'var(--color-border)'}`,
                      borderRadius: '50%',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
                      color: purchased ? 'var(--color-teal)' : 'var(--color-text-muted)',
                    }}>
                      {purchased ? <Eye size={12} /> : i + 1}
                    </div>
                    <div style={{ flex: 1 }}>
                      {purchased ? (
                        <p style={{ color: 'var(--color-text)', lineHeight: 1.6 }}>{hint.text}</p>
                      ) : (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                          <span className="text-muted" style={{ fontSize: '0.9rem' }}>Hint #{i + 1} — locked</span>
                          <button
                            className="btn btn-ghost"
                            onClick={() => unlockHint(i)}
                            disabled={unlocking !== null}
                            style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                          >
                            {unlocking === i
                              ? <span className="spinner" style={{ width: 12, height: 12 }} />
                              : null}
                            Unlock (−{hint.cost} pts)
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Reference links */}
        {challenge.refs && challenge.refs.length > 0 && (
          <div className="card" style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
              References
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {challenge.refs.map(ref => (
                <a key={ref.url} href={ref.url} target="_blank" rel="noreferrer"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: 'var(--color-teal)', fontSize: '0.9rem' }}>
                  <ExternalLink size={13} /> {ref.label}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Prev / Next navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '0.5rem' }}>
          {prev ? (
            <button className="btn btn-ghost" onClick={() => navigate(`/challenges/${prev.id}`)} style={{ fontSize: '0.85rem' }}>
              <ArrowLeft size={14} /> {prev.title}
            </button>
          ) : <div />}
          {next && (
            <button className="btn btn-secondary" onClick={() => navigate(`/challenges/${next.id}`)} style={{ fontSize: '0.85rem', marginLeft: 'auto' }}>
              {next.title} <ArrowRight size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Confirm hint modal */}
      {confirmHint && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, padding: '1rem',
        }}>
          <div className="card" style={{ maxWidth: 380, width: '100%', textAlign: 'center' }}>
            <AlertTriangle size={36} color="var(--color-warning)" style={{ marginBottom: '1rem' }} />
            <h3 style={{ marginBottom: '0.5rem' }}>Use Hint?</h3>
            <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.9rem' }}>
              This hint costs <strong style={{ color: 'var(--color-red)' }}>{confirmHint.cost} points</strong>. The deduction is immediate and permanent.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button className="btn btn-ghost" onClick={() => setConfirmHint(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={confirmUnlock}>Use Hint (−{confirmHint.cost} pts)</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
