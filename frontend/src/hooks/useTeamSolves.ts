import { useState, useEffect } from 'react'
import api from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

/**
 * Returns a Set of challenge slugs solved by the current user's team.
 * Fetches on every mount — the endpoint is a single indexed DB query.
 */
export function useTeamSolves(): Set<string> {
  const { user } = useAuthStore()
  const [solved, setSolved] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!user) return
    api.get<string[]>('/solves/my')
      .then(r => setSolved(new Set(r.data)))
      .catch(() => {})
  }, [user?.id])

  return solved
}

export function invalidateSolvesCache() {
  // No-op — kept for API compatibility, no cache to invalidate
}
