/**
 * Fetches and caches the team environment data.
 * Used by EnvVar/EnvVarInline inside challenge MDX files.
 * Returns null while loading or if user has no team.
 */
import { useState, useEffect } from 'react'
import { teamsApi, type TeamEnvironment } from '@/utils/api'
import { useAuthStore } from '@/store/authStore'

// Module-level cache so repeated mounts don't re-fetch
let _cache: TeamEnvironment | null = null
let _promise: Promise<void> | null = null

export function useEnvData(): TeamEnvironment | null {
  const { user } = useAuthStore()
  const [env, setEnv] = useState<TeamEnvironment | null>(_cache)

  useEffect(() => {
    if (!user?.team_id) return
    if (_cache) { setEnv(_cache); return }
    if (!_promise) {
      _promise = teamsApi.myEnvironment()
        .then(r => { _cache = r.data })
        .catch(() => {})
    }
    _promise.then(() => { if (_cache) setEnv(_cache) })
  }, [user?.team_id])

  return env
}

/** Call this to invalidate the cache (e.g. after team change) */
export function invalidateEnvCache() {
  _cache = null
  _promise = null
}
