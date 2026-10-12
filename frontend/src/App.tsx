import { useEffect, useState } from 'react'
import { type Account, type Dashboard, type EventType, getDashboard, importArchive, sync } from './api'
import { FollowerChart } from './FollowerChart'
import { formatDate } from './format'

const EVENT_LABEL: Record<EventType, string> = {
  new_follow: 'New follow',
  unfollow: 'Unfollow',
  exit: 'Exit (account gone)',
}

function AccountCell({ account }: { account: Account }) {
  const href = account.username ? `https://x.com/${account.username}` : `https://x.com/i/user/${account.id}`
  return (
    <a className="account" href={href} target="_blank" rel="noreferrer">
      {account.avatar_url ? <img src={account.avatar_url} alt="" /> : <span className="avatar-placeholder" />}
      <span>
        <strong>{account.name ?? 'Unknown'}</strong>
        <span className="muted"> {account.username ? `@${account.username}` : `id ${account.id}`}</span>
      </span>
    </a>
  )
}

function Setup({ data, onDone }: { data: Dashboard; onDone: () => void }) {
  const [path, setPath] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!data.archive_imported) {
    return (
      <section className="card">
        <h2>1. Import your X archive</h2>
        <p className="muted">
          The zip you downloaded from X becomes the first Snapshot. Sync stays locked until then.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            importArchive(path).then(onDone, (err: Error) => setError(err.message))
          }}
        >
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="~/Downloads/twitter-….zip"
            aria-label="Archive path"
          />
          <button disabled={!path}>Import</button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>
    )
  }
  if (!data.authenticated) {
    return (
      <section className="card">
        <h2>2. Connect your X account</h2>
        <p className="muted">Only needed once: the token stays on the backend and refreshes itself.</p>
        <a className="button" href="/api/auth/login">
          Log in with X
        </a>
      </section>
    )
  }
  return null
}

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [filter, setFilter] = useState<EventType | 'all'>('all')
  const [churnersOnly, setChurnersOnly] = useState(false)

  const load = () => getDashboard().then(setData, (err: Error) => setError(err.message))
  useEffect(() => {
    load()
  }, [])

  if (!data) return <main>{error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>}</main>

  const runSync = () => {
    setSyncing(true)
    setError(null)
    sync()
      .then(load, (err: Error) => setError(err.message))
      .finally(() => setSyncing(false))
  }

  const events = data.events.filter((e) => (filter === 'all' || e.type === filter) && (!churnersOnly || e.churner))
  const ready = data.archive_imported && data.authenticated

  return (
    <main>
      <header>
        <h1>Follower tracker</h1>
        <div className="sync">
          <span className="muted">
            {data.last_snapshot_at ? `Last Snapshot: ${formatDate(data.last_snapshot_at)}` : 'No Snapshot yet'}
            {' · '}
            spent this month ${data.spend.month_usd.toFixed(3)} / ${data.spend.budget_usd.toFixed(2)}
          </span>
          <button onClick={runSync} disabled={!ready || syncing}>
            {syncing ? 'Syncing…' : 'Sync'}
          </button>
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      <Setup data={data} onDone={load} />

      <section className="stats">
        <div>
          <span className="label">Followers</span>
          <span className="value">{data.counts.followers}</span>
        </div>
        <div>
          <span className="label">Following</span>
          <span className="value">{data.counts.following}</span>
        </div>
        <div>
          <span className="label">Mutuals</span>
          <span className="value">{data.counts.mutuals}</span>
        </div>
        <div>
          <span className="label">Unfollows (30 days)</span>
          <span className="value">{data.counts.unfollows_30d}</span>
        </div>
      </section>

      <section className="card">
        <h2>Followers over time</h2>
        <FollowerChart history={data.follower_history} />
      </section>

      <section className="card">
        <h2>Events</h2>
        <div className="filters">
          {(['all', 'new_follow', 'unfollow', 'exit'] as const).map((f) => (
            <button key={f} className={filter === f ? 'chip active' : 'chip'} onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : EVENT_LABEL[f]}
            </button>
          ))}
          <label>
            <input type="checkbox" checked={churnersOnly} onChange={(e) => setChurnersOnly(e.target.checked)} /> Follow-churners
            only
          </label>
        </div>
        {events.length === 0 ? (
          <p className="muted">No events.</p>
        ) : (
          <ul className="list">
            {events.map((e) => (
              <li key={`${e.type}-${e.account.id}-${e.between[1]}`}>
                <AccountCell account={e.account} />
                <span className={`tag ${e.type}`}>{EVENT_LABEL[e.type]}</span>
                {e.churner && <span className="tag churner">Follow-churner</span>}
                {e.type === 'unfollow' && e.still_following && <span className="tag">you still follow them</span>}
                <span className="muted when">
                  between {formatDate(e.between[0])} and {formatDate(e.between[1])}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Not following you back ({data.one_way_following.length})</h2>
        {data.one_way_following.length === 0 ? (
          <p className="muted">Nobody.</p>
        ) : (
          <ul className="list">
            {data.one_way_following.map((a) => (
              <li key={a.id}>
                <AccountCell account={a} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
