import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { LogOut, Shield, LayoutDashboard, Trophy, Users, Server, Activity } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useEnvData } from '@/hooks/useEnvData'

export default function Header() {
  const { user, clearAuth } = useAuthStore()
  const env = useEnvData()
  const [showJoinCode, setShowJoinCode] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const logout = () => {
    clearAuth()
    navigate('/login')
  }

  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(path + '/')

  return (
    <header style={{
      background: 'var(--color-surface)',
      borderBottom: '1px solid var(--color-border)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Top brand bar */}
      <div style={{
        background: 'linear-gradient(90deg, var(--color-red) 0%, #8b1510 50%, transparent 100%)',
        height: '3px',
      }} />

      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '0 1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        height: '60px',
      }}>
        {/* Logo area */}
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', textDecoration: 'none' }}>
          <div style={{
            width: 32, height: 32,
            background: 'var(--color-red)',
            borderRadius: '6px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Shield size={18} color="white" />
          </div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', color: 'var(--color-text)', lineHeight: 1.1 }}>
              XPERTS<span style={{ color: 'var(--color-red)' }}>26</span>
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              vWAN CTF
            </div>
          </div>
        </Link>

        {/* Nav */}
        {user && (
          <nav style={{ display: 'flex', gap: '0.25rem', marginLeft: '1rem', flex: 1 }}>
            <NavLink to="/challenges" label="Challenges" icon={<LayoutDashboard size={15} />} active={isActive('/challenges')} />
            {user.team_id && (
              <NavLink to="/environment" label="My Environment" icon={<Server size={15} />} active={isActive('/environment')} />
            )}
            <NavLink to="/scoreboard" label="Scoreboard" icon={<Trophy size={15} />} active={isActive('/scoreboard')} />
            {user.role === 'trainer' && (
              <NavLink to="/trainer" label="Admin" icon={<Users size={15} />} active={isActive('/trainer')} />
            )}
            {user.role === 'trainer' && (
              <NavLink to="/progress" label="Progress" icon={<Activity size={15} />} active={isActive('/progress')} />
            )}
          </nav>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {user ? (
            <>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text)' }}>{user.username}</div>
                {user.team_name && (
                  <div
                    style={{ fontSize: '0.7rem', color: 'var(--color-teal)', letterSpacing: '0.05em', position: 'relative', cursor: 'default', userSelect: 'none' }}
                    onMouseEnter={() => setShowJoinCode(true)}
                    onMouseLeave={() => setShowJoinCode(false)}
                  >
                    {user.team_name}
                    {showJoinCode && env?.join_code && (
                      <div style={{
                        position: 'absolute', right: 0, top: '100%', marginTop: '4px',
                        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)', padding: '0.4rem 0.75rem',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                        whiteSpace: 'nowrap', zIndex: 200,
                      }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.15rem' }}>Join code</div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--color-text)', fontWeight: 700, letterSpacing: '0.1em' }}>{env.join_code}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <button className="btn btn-ghost" onClick={logout} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
                <LogOut size={14} />
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
              Login
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}

function NavLink({ to, label, icon, active }: { to: string; label: string; icon: React.ReactNode; active: boolean }) {
  return (
    <Link
      to={to}
      style={{
        display: 'flex', alignItems: 'center', gap: '0.4rem',
        padding: '0.4rem 0.75rem',
        borderRadius: 'var(--radius-md)',
        fontFamily: 'var(--font-display)',
        fontWeight: 600,
        fontSize: '0.9rem',
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        color: active ? 'var(--color-teal)' : 'var(--color-text-muted)',
        background: active ? 'rgba(0,212,212,0.08)' : 'transparent',
        border: active ? '1px solid rgba(0,212,212,0.2)' : '1px solid transparent',
        textDecoration: 'none',
        transition: 'all 0.15s',
      }}
    >
      {icon}
      {label}
    </Link>
  )
}
