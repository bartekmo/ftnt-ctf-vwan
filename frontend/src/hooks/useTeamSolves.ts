import { useState, useEffect } from 'react'
import api from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

/**
 * Returns a map of challenge slug -> points_awarded for the current user's team.
 * Use .has(slug) to check if solved, .get(slug) to get points awarded.
 * Fetches on every mount — the endpoint is a single indexed DB query.
 */
export function useTeamSolves(): Map<string, number> {
  const { user } = useAuthStore()
  const [solved, setSolved] = useState<Map<string, number>>(new Map())

  useEffect(() => {
    if (!user) return
    api.get<Record<string, number>>('/solves/my')
      .then(r => setSolved(new Map(Object.entries(r.data))))
      .catch(() => {})
  }, [user?.id])

  return solved
}

export function invalidateSolvesCache() {
  // No-op — kept for API compatibility, no cache to invalidate
}
