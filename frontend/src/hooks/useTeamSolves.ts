import { useState, useEffect } from 'react'
import api from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

let _cache: Set<string> | null = null
let _promise: Promise<Set<string>> | null = null

async function fetchSolvedSlugs(): Promise<Set<string>> {
  const r = await api.get<string[]>('/my/solves')
  return new Set(r.data)
}

/**
 * Returns a Set of challenge slugs solved by the current user's team.
 * Cached for the lifetime of the page session.
 */
export function useTeamSolves(): Set<string> {
  const { user } = useAuthStore()
  const [solved, setSolved] = useState<Set<string>>(_cache ?? new Set())

  useEffect(() => {
    if (!user) return
    if (_cache) { setSolved(_cache); return }
    if (!_promise) {
      _promise = fetchSolvedSlugs()
        .then(s => { _cache = s; return s })
        .catch(() => new Set<string>())
    }
    _promise.then(s => setSolved(s))
  }, [user?.id])

  return solved
}

export function invalidateSolvesCache() {
  _cache = null
  _promise = null
}
