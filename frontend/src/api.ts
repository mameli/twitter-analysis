export type Account = {
  id: string
  username: string | null
  name: string | null
  avatar_url: string | null
}

export type EventType = 'new_follow' | 'unfollow' | 'exit'

export type FollowerEvent = {
  type: EventType
  account: Account
  between: [string, string]
  churner: boolean
  still_following: boolean
}

export type Dashboard = {
  archive_imported: boolean
  authenticated: boolean
  last_snapshot_at: string | null
  counts: { followers: number; following: number; mutuals: number; unfollows_30d: number }
  follower_history: { taken_at: string; followers: number }[]
  events: FollowerEvent[]
  one_way_following: Account[]
  spend: { month_usd: number; budget_usd: number }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const detail = await r.json().then((b) => b.detail, () => r.statusText)
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return r.json()
}

export const getDashboard = () => request<Dashboard>('GET', '/dashboard')
export const importArchive = (path: string) => request('POST', '/archive', { path })
export const sync = () => request('POST', '/sync')
