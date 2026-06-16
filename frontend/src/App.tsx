import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/utils/api'
import Header from '@/components/shared/Header'
import AuthPage from '@/pages/AuthPage'
import TeamLobbyPage from '@/pages/TeamLobbyPage'
import ChallengesPage from '@/pages/ChallengesPage'
import ChallengeDetailPage from '@/pages/ChallengeDetailPage'
import EnvironmentPage from '@/pages/EnvironmentPage'
import ScoreboardPage from '@/pages/ScoreboardPage'
import TrainerPage from '@/pages/TrainerPage'
import ProgressPage from '@/pages/ProgressPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function RequireTrainer({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'trainer') return <Navigate to="/challenges" replace />
  return <>{children}</>
}

const USER_REFRESH_INTERVAL_MS = 30_000

/**
 * Keeps the cached user (localStorage + store) in sync with the server.
 * Fixes stale team_name/team_id/role shown in the Header after a trainer
 * moves a user between teams or changes their role — the JWT and the
 * cached user object are otherwise only set once, at login, and never
 * refreshed on their own.
 */
function useUserRefresh() {
  const { user, token, setAuth } = useAuthStore()

  useEffect(() => {
    if (!user || !token) return

    const refresh = async () => {
      try {
        const r = await authApi.me()
        setAuth(r.data, token)
      } catch {
        // Network hiccup or expired token — the existing 401 interceptor
        // in api.ts already handles redirecting to /login on auth failure.
      }
    }

    refresh()
    const interval = setInterval(refresh, USER_REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [user?.id, token])
}

export default function App() {
  useUserRefresh()
  return (
    <BrowserRouter>
      <Header />
      <main style={{ flex: 1 }}>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route path="/scoreboard" element={<ScoreboardPage />} />

          <Route path="/team" element={
            <RequireAuth><TeamLobbyPage /></RequireAuth>
          } />
          <Route path="/challenges" element={
            <RequireAuth><ChallengesPage /></RequireAuth>
          } />
          <Route path="/challenges/:id" element={
            <RequireAuth><ChallengeDetailPage /></RequireAuth>
          } />
          <Route path="/environment" element={
            <RequireAuth><EnvironmentPage /></RequireAuth>
          } />
          <Route path="/trainer" element={
            <RequireTrainer><TrainerPage /></RequireTrainer>
          } />
          <Route path="/progress" element={
            <RequireTrainer><ProgressPage /></RequireTrainer>
          } />

          <Route path="/" element={<Navigate to="/challenges" replace />} />
          <Route path="*" element={<Navigate to="/challenges" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
