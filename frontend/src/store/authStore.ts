import { create } from 'zustand'
import type { User } from '@/utils/api'

interface AuthState {
  user: User | null
  token: string | null
  setAuth: (user: User, token: string) => void
  clearAuth: () => void
  isTrainer: () => boolean
}

const storedUser = localStorage.getItem('ctf_user')
const storedToken = localStorage.getItem('ctf_token')

export const useAuthStore = create<AuthState>((set, get) => ({
  user: storedUser ? JSON.parse(storedUser) : null,
  token: storedToken,
  setAuth: (user, token) => {
    localStorage.setItem('ctf_token', token)
    localStorage.setItem('ctf_user', JSON.stringify(user))
    set({ user, token })
  },
  clearAuth: () => {
    localStorage.removeItem('ctf_token')
    localStorage.removeItem('ctf_user')
    set({ user: null, token: null })
  },
  isTrainer: () => get().user?.role === 'trainer',
}))
