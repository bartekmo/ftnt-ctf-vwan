import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT automatically
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ctf_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Handle 401 globally
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ctf_token')
      localStorage.removeItem('ctf_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Types ── (mirrors backend schemas)
export interface User {
  id: number
  username: string
  email: string
  role: 'attendee' | 'trainer'
  team_id: number | null
  team_name: string | null
}

export interface Team {
  id: number
  name: string
  join_code: string
  env_id: string | null
  member_count: number
  score: number
  created_at: string
}

export interface TeamDetail extends Team {
  members: User[]
}

export interface TeamEnvironment {
  team_id: number
  team_name: string
  env_id: string
  azure_username: string
  azure_password: string
  rg_name: string
  fgt_asn: number
  azure_asn: number
  overlay_network: string
  sdwan_healthcheck_range: string
  fgt_nva1_name: string
  fgt_nva1_pip: string
  fgt_nva2_name: string
  fgt_nva2_pip: string
  flex_token1: string
  flex_token2: string
  spoke_cidr: string
  spoke_server_private: string
  spoke_server_public: string
  spoke_peered: boolean
  branch_cidr: string
  branch_fgt_pip: string
  branch_win_pip: string
  fmg_serial: string
  fmg_ip: string
}

export interface Challenge {
  id: number
  title: string
  description: string
  category: string
  base_points: number
  is_visible: boolean
  order_index: number
  hint_count: number
  solve_count: number
  is_solved_by_team: boolean
}

export interface Hint {
  id: number
  challenge_id: number
  points_cost: number
  order_index: number
  content: string | null
  is_purchased: boolean
}

export interface HintUse {
  hint_id: number
  team_id: number
  team_name: string
  challenge_title: string
  points_cost: number
  used_at: string
}

export interface ScoreboardEntry {
  rank: number
  team_id: number
  team_name: string
  score: number
  solve_count: number
  hint_cost: number
}

export interface Scoreboard {
  entries: ScoreboardEntry[]
  event_status: 'pending' | 'running' | 'paused' | 'finished'
  last_updated: string
}

export interface CTFEvent {
  id: number
  name: string
  status: 'pending' | 'running' | 'paused' | 'finished'
  started_at: string | null
  finished_at: string | null
  first_blood_bonus: number
}

// ── API Methods ──

export const authApi = {
  register: (data: { username: string; email: string; password: string }) =>
    api.post<{ access_token: string; user: User }>('/auth/register', data),
  login: (username: string, password: string) =>
    api.post<{ access_token: string; user: User }>('/auth/login', { username, password }),
  me: () => api.get<User>('/auth/me'),
}

export const teamsApi = {
  list: () => api.get<Team[]>('/teams'),
  create: (name: string) => api.post<Team>('/teams', { name }),
  join: (join_code: string) => api.post<Team>('/teams/join', { join_code }),
  leave: () => api.post('/teams/leave'),
  get: (id: number) => api.get<TeamDetail>(`/teams/${id}`),
  myEnvironment: () => api.get<TeamEnvironment>('/teams/my/environment'),
  getEnvironment: (id: number) => api.get<TeamEnvironment>(`/teams/${id}/environment`),
  shuffle: () => api.post('/teams/admin/shuffle'),
  moveUser: (user_id: number, team_id: number | null) =>
    api.put('/teams/admin/move', { user_id, team_id }),
}

export const challengesApi = {
  list: () => api.get<Challenge[]>('/challenges'),
  get: (id: number) => api.get<Challenge>(`/challenges/${id}`),
  hints: (id: number) => api.get<Hint[]>(`/challenges/${id}/hints`),
  unlockHint: (challengeId: number, hintId: number) =>
    api.post<Hint>(`/challenges/${challengeId}/hints/${hintId}/unlock`),
  create: (data: Partial<Challenge>) => api.post<Challenge>('/challenges', data),
  update: (id: number, data: Partial<Challenge>) => api.put<Challenge>(`/challenges/${id}`, data),
  delete: (id: number) => api.delete(`/challenges/${id}`),
  createHint: (challengeId: number, data: Partial<Hint>) =>
    api.post<Hint>(`/challenges/${challengeId}/hints`, data),
  allHintUses: () => api.get<HintUse[]>('/challenges/admin/hint-uses'),
}

export const scoreboardApi = {
  get: () => api.get<Scoreboard>('/scoreboard'),
  getEvent: () => api.get<CTFEvent>('/event'),
  updateEvent: (data: Partial<CTFEvent>) => api.put<CTFEvent>('/event', data),
  resetEvent: () => api.post('/event/reset'),
}

export const usersApi = {
  list: () => api.get<User[]>('/users'),
  setRole: (userId: number, role: string) => api.put(`/users/${userId}/role?role=${role}`),
}
// ── Infra API ──

export interface HubDetailOut {
  name: string
  location: string
}

export interface SrvOut {
  private: string | null
  public: string | null
}

export interface FmgOut {
  serial: string
  ip: string
}

export const infraApi = {
  fmg: () => api.get<FmgOut>('/infra/fmg'),
  srv: (hubName: string) => api.get<SrvOut>(`/infra/hubs/${hubName}/srv`),
  hub: (hubName: string) => api.get<HubDetailOut>(`/infra/hubs/${hubName}`),
}
