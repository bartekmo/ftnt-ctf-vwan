import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import Header from '@/components/shared/Header'
import AuthPage from '@/pages/AuthPage'
import TeamLobbyPage from '@/pages/TeamLobbyPage'
import ChallengesPage from '@/pages/ChallengesPage'
import ChallengeDetailPage from '@/pages/ChallengeDetailPage'
import ScoreboardPage from '@/pages/ScoreboardPage'
import TrainerPage from '@/pages/TrainerPage'

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

export default function App() {
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
          <Route path="/trainer" element={
            <RequireTrainer><TrainerPage /></RequireTrainer>
          } />

          <Route path="/" element={<Navigate to="/challenges" replace />} />
          <Route path="*" element={<Navigate to="/challenges" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
