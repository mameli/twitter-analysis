import { useState } from 'react'
import { formatDate } from './format'

type Point = { taken_at: string; followers: number }

const W = 720
const H = 220
const PAD = { top: 16, right: 16, bottom: 28, left: 44 }

export function FollowerChart({ history }: { history: Point[] }) {
  const [hover, setHover] = useState<number | null>(null)

  if (history.length < 2) {
    return <p className="muted">The chart appears after the first Sync.</p>
  }

  const times = history.map((p) => new Date(p.taken_at).getTime())
  const values = history.map((p) => p.followers)
  const [t0, t1] = [times[0], times[times.length - 1]]
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const pad = Math.max(2, Math.ceil((hi - lo) * 0.15))
  const [y0, y1] = [lo - pad, hi + pad]

  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0 || 1)) * (W - PAD.left - PAD.right)
  const y = (v: number) => PAD.top + (1 - (v - y0) / (y1 - y0)) * (H - PAD.top - PAD.bottom)
  const ticks = [...new Set([lo, Math.round((lo + hi) / 2), hi])]

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const mx = ((e.clientX - box.left) / box.width) * W
    let best = 0
    times.forEach((t, i) => {
      if (Math.abs(x(t) - mx) < Math.abs(x(times[best]) - mx)) best = i
    })
    setHover(best)
  }

  const path = history.map((p, i) => `${i ? 'L' : 'M'}${x(times[i])},${y(p.followers)}`).join(' ')
  const h = hover !== null ? history[hover] : null

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Followers over time"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
            <text className="axis" x={PAD.left - 8} y={y(v)} textAnchor="end" dominantBaseline="middle">
              {v}
            </text>
          </g>
        ))}
        <text className="axis" x={PAD.left} y={H - 8}>{formatDate(history[0].taken_at)}</text>
        <text className="axis" x={W - PAD.right} y={H - 8} textAnchor="end">
          {formatDate(history[history.length - 1].taken_at)}
        </text>
        <path className="line" d={path} />
        {history.map((p, i) => (
          <circle key={p.taken_at} className="dot" cx={x(times[i])} cy={y(p.followers)} r={hover === i ? 5 : 3} />
        ))}
        {h && hover !== null && (
          <line className="crosshair" x1={x(times[hover])} x2={x(times[hover])} y1={PAD.top} y2={H - PAD.bottom} />
        )}
      </svg>
      {h && hover !== null && (
        <div className="tooltip" style={{ left: `${(x(times[hover]) / W) * 100}%` }}>
          <strong>{h.followers}</strong> followers
          <br />
          <span className="muted">{formatDate(h.taken_at)}</span>
        </div>
      )}
      <details>
        <summary>Table</summary>
        <table>
          <tbody>
            {history.map((p) => (
              <tr key={p.taken_at}>
                <td>{formatDate(p.taken_at)}</td>
                <td className="num">{p.followers}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
