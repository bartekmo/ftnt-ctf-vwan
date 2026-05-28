import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Lock, ChevronRight, BookOpen } from 'lucide-react'
import { challenges } from '@/utils/challenges'
import { useAuthStore } from '@/store/authStore'

const CATEGORY_COLORS: Record<string, string> = {
  networking: 'badge-teal',
  security:   'badge-red',
  routing:    'badge-teal',
  vpn:        'badge-red',
  monitoring: 'badge-gray',
  misc:       'badge-gray',
}

export default function ChallengesPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  // Filter hidden challenges (trainers see all)
  const visible = challenges.filter(c => c.visible || user?.role === 'trainer')

  return (
    <div className="page-enter" style={{ maxWidth: 1000, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <div style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Challenges</h2>
          <p className="text-muted" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
            {user?.team_name && <><span className="text-teal">{user.team_name}</span> · </>}
            {visible.length} challenge{visible.length !== 1 ? 's' : ''} · complete in order
          </p>
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '4rem', color: 'var(--color-text-muted)' }}>
          <Lock size={40} style={{ marginBottom: '1rem', opacity: 0.3 }} />
          <p>No challenges available yet.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {visible.map((challenge, idx) => (
            <div
              key={challenge.id}
              className="card card-hover"
              onClick={() => navigate(`/challenges/${challenge.id}`)}
              style={{
                display: 'flex', alignItems: 'center', gap: '1rem',
                padding: '1rem 1.25rem',
              }}
            >
              {/* Order number */}
              <div style={{
                width: 36, height: 36, flexShrink: 0, borderRadius: '50%',
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  {String(idx + 1).padStart(2, '0')}
                </span>
              </div>

              {/* Title + meta */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.05rem' }}>
                  {challenge.title}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <span className={`badge ${CATEGORY_COLORS[challenge.category] ?? 'badge-gray'}`} style={{ fontSize: '0.65rem' }}>
                    {challenge.category}
                  </span>
                  {challenge.hints && challenge.hints.length > 0 && (
                    <span className="tag">{challenge.hints.length} hint{challenge.hints.length !== 1 ? 's' : ''}</span>
                  )}
                  {!challenge.scored && (
                    <span className="badge badge-gray" style={{ fontSize: '0.65rem' }}>informational</span>
                  )}
                </div>
              </div>

              {/* Points */}
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                {challenge.scored && challenge.points > 0 ? (
                  <>
                    <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.25rem', color: 'var(--color-red)' }}>
                      {challenge.points}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>pts</div>
                  </>
                ) : (
                  <BookOpen size={18} color="var(--color-text-dim)" />
                )}
              </div>

              <ChevronRight size={16} color="var(--color-text-dim)" style={{ flexShrink: 0 }} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
