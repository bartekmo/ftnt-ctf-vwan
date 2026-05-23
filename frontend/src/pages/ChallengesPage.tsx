import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Lock, ChevronRight } from 'lucide-react'
import { challengesApi, type Challenge } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

const CATEGORY_COLORS: Record<string, string> = {
  networking: 'badge-teal',
  security: 'badge-red',
  routing: 'badge-teal',
  vpn: 'badge-red',
  monitoring: 'badge-gray',
  misc: 'badge-gray',
}

export default function ChallengesPage() {
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [loading, setLoading] = useState(true)
  const { user } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (!user?.team_id && user?.role !== 'trainer') {
      navigate('/team')
      return
    }
    challengesApi.list().then(r => {
      setChallenges(r.data)
      setLoading(false)
    })
  }, [user, navigate])

  const categories = Array.from(new Set(challenges.map(c => c.category)))
  const solved = challenges.filter(c => c.is_solved_by_team).length

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <span className="spinner" style={{ width: 32, height: 32 }} />
    </div>
  )

  return (
    <div className="page-enter" style={{ maxWidth: 1000, margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Page header */}
      <div style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Challenges</h2>
          <p className="text-muted" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
            {user?.team_name && <><span className="text-teal">{user.team_name}</span> · </>}
            {solved}/{challenges.length} solved
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {categories.map(cat => (
            <span key={cat} className={`badge ${CATEGORY_COLORS[cat] ?? 'badge-gray'}`}>{cat}</span>
          ))}
        </div>
      </div>

      {challenges.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '4rem', color: 'var(--color-text-muted)' }}>
          <Lock size={40} style={{ marginBottom: '1rem', opacity: 0.3 }} />
          <p>No challenges available yet. The CTF hasn't started.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {challenges.map(challenge => (
            <ChallengeRow
              key={challenge.id}
              challenge={challenge}
              onClick={() => navigate(`/challenges/${challenge.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ChallengeRow({ challenge, onClick }: { challenge: Challenge; onClick: () => void }) {
  const solved = challenge.is_solved_by_team

  return (
    <div
      className="card card-hover"
      onClick={onClick}
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        padding: '1rem 1.25rem',
        borderColor: solved ? 'rgba(34,197,94,0.3)' : 'var(--color-border)',
        overflow: 'hidden',
      }}
    >
      {solved && <div className="solved-overlay" />}

      {/* Solved icon / order index */}
      <div style={{
        width: 36, height: 36, flexShrink: 0,
        borderRadius: '50%',
        background: solved ? 'rgba(34,197,94,0.15)' : 'var(--color-surface-2)',
        border: `1px solid ${solved ? 'rgba(34,197,94,0.3)' : 'var(--color-border)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {solved
          ? <CheckCircle2 size={18} color="#4ade80" />
          : <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{String(challenge.order_index + 1).padStart(2, '0')}</span>
        }
      </div>

      {/* Title + category */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.05rem', color: solved ? '#4ade80' : 'var(--color-text)' }}>
          {challenge.title}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={`badge ${CATEGORY_COLORS[challenge.category] ?? 'badge-gray'}`} style={{ fontSize: '0.65rem' }}>{challenge.category}</span>
          {challenge.hint_count > 0 && (
            <span className="tag">{challenge.hint_count} hints</span>
          )}
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)' }}>
            {challenge.solve_count} solve{challenge.solve_count !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Points */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.25rem', color: 'var(--color-red)' }}>
          {challenge.base_points}
        </div>
        <div style={{ fontSize: '0.65rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>pts</div>
      </div>

      <ChevronRight size={16} color="var(--color-text-dim)" style={{ flexShrink: 0 }} />
    </div>
  )
}
