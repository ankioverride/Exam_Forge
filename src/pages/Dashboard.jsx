import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { fetchAttempts } from '../lib/auth'
import { EXAM_CONFIG } from '../data/questions'

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtTime(secs) {
  if (!secs) return '—'
  const m = Math.floor(secs / 60), s = secs % 60
  return `${m}m ${s}s`
}

function pct(attempt) {
  return Math.round((attempt.score / attempt.maxScore) * 100)
}

// ── Sparkline (pure SVG) ─────────────────────────────────────────────────────

function Sparkline({ data }) {
  if (!data || data.length < 2) return null
  const W = 200, H = 48, pad = 4
  const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (W - pad * 2))
  const ys = data.map(v => H - pad - ((v / 100) * (H - pad * 2)))
  const points = xs.map((x, i) => `${x},${ys[i]}`).join(' ')
  return (
    <svg width={W} height={H} className="overflow-visible">
      <polyline points={points} fill="none" stroke="#e8a020" strokeWidth="1.5" strokeLinejoin="round" />
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r="2.5" fill="#e8a020" />
      ))}
    </svg>
  )
}

// ── Subject Accuracy Heatmap ─────────────────────────────────────────────────

function SubjectHeatmap({ attempts }) {
  const subjectMap = useMemo(() => {
    const map = {}
    attempts.forEach(a => {
      // Prefer subjectBreakdown if available
      if (a.subjectBreakdown && a.subjectBreakdown.length > 0) {
        a.subjectBreakdown.forEach(({ subject, correct, total }) => {
          if (!subject) return
          if (!map[subject]) map[subject] = { correct: 0, total: 0 }
          map[subject].correct += correct
          map[subject].total   += total
        })
      } else if (a.questions && a.answers) {
        a.questions.forEach((q, i) => {
          const sub = q.subject || 'General'
          if (!map[sub]) map[sub] = { correct: 0, total: 0 }
          map[sub].total++
          if (a.answers[i] === q.correct) map[sub].correct++
        })
      }
    })
    return map
  }, [attempts])

  const subjects = Object.entries(subjectMap)
    .map(([name, v]) => ({ name, pct: Math.round((v.correct / v.total) * 100), correct: v.correct, total: v.total }))
    .sort((a, b) => a.pct - b.pct)

  if (subjects.length === 0) return null

  function cellBg(p) {
    if (p < 40) return 'bg-wrong/20 border-wrong/20'
    if (p < 60) return 'bg-gold/15 border-gold/20'
    return 'bg-correct/15 border-correct/20'
  }

  function cellText(p) {
    if (p < 40) return 'text-wrong'
    if (p < 60) return 'text-gold'
    return 'text-correct'
  }

  return (
    <>
      <p className="section-title mt-8">Subject Accuracy</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 mb-8">
        {subjects.map(s => (
          <div
            key={s.name}
            className={`border p-3 flex flex-col gap-1 ${cellBg(s.pct)}`}
          >
            <span className="text-xs text-ink leading-tight truncate font-sans" title={s.name}>{s.name}</span>
            <span className={`font-mono text-lg font-semibold leading-none ${cellText(s.pct)}`}>
              {s.pct}%
            </span>
            <span className="font-mono text-[0.6rem] text-muted tracking-wider">
              {s.correct}/{s.total} correct
            </span>
          </div>
        ))}
      </div>
    </>
  )
}

// ── Mode Badge ───────────────────────────────────────────────────────────────

function ModeBadge({ mode }) {
  if (!mode) return null
  if (mode === 'timed') return <span className="tag tag-red">Timed</span>
  return <span className="tag tag-grey">Practice</span>
}

// ── Exam Filter Tabs ─────────────────────────────────────────────────────────

const EXAM_TABS = [
  { id: 'all',  label: 'All' },
  { id: 'upsc', label: 'UPSC' },
  { id: 'apsc', label: 'APSC' },
  { id: 'cat',  label: 'CAT' },
]

function ExamTabs({ active, onChange }) {
  return (
    <div className="flex items-center gap-1 border border-border bg-surface p-1 w-fit mb-8">
      {EXAM_TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`
            font-mono text-xs tracking-widest uppercase px-4 py-1.5 border transition-colors duration-100
            ${active === tab.id
              ? 'bg-gold/10 text-gold border-gold/30'
              : 'text-muted hover:text-ink border-transparent'
            }
          `}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

// ── Per-exam breakdown stat row ──────────────────────────────────────────────

function ExamBreakdown({ attempts, examId }) {
  if (examId === 'all' || attempts.length === 0) return null

  const cfg = EXAM_CONFIG[examId] || {}
  const avgScoreVal = (attempts.reduce((s, a) => s + pct(a), 0) / attempts.length).toFixed(1)
  const bestVal     = Math.max(...attempts.map(a => pct(a)))
  const totalTime   = attempts.reduce((s, a) => s + (a.timeTaken || 0), 0)

  return (
    <div className="mb-8 bg-surface border border-border p-4 flex flex-wrap gap-6">
      <div>
        <p className="font-mono text-[0.6rem] tracking-widest uppercase text-muted mb-0.5">
          {cfg.name || examId} — Tests
        </p>
        <p className="font-mono text-xl font-semibold text-bright">{attempts.length}</p>
      </div>
      <div>
        <p className="font-mono text-[0.6rem] tracking-widest uppercase text-muted mb-0.5">Avg Score</p>
        <p className="font-mono text-xl font-semibold text-bright">{avgScoreVal}%</p>
      </div>
      <div>
        <p className="font-mono text-[0.6rem] tracking-widest uppercase text-muted mb-0.5">Best Score</p>
        <p className="font-mono text-xl font-semibold text-correct">{bestVal}%</p>
      </div>
      <div>
        <p className="font-mono text-[0.6rem] tracking-widest uppercase text-muted mb-0.5">Avg Time</p>
        <p className="font-mono text-xl font-semibold text-bright">
          {attempts.length ? fmtTime(Math.round(totalTime / attempts.length)) : '—'}
        </p>
      </div>
    </div>
  )
}

// ── Score Trend Card ─────────────────────────────────────────────────────────

function ScoreTrendCard({ attempts }) {
  const last10 = useMemo(() => {
    return [...attempts]
      .sort((a, b) => new Date(a.date) - new Date(b.date))
      .slice(-10)
      .map(a => pct(a))
  }, [attempts])

  if (last10.length < 2) return null

  const latest = last10[last10.length - 1]
  const prev   = last10[last10.length - 2]
  const delta  = latest - prev
  const deltaColor = delta > 0 ? 'text-correct' : delta < 0 ? 'text-wrong' : 'text-muted'
  const deltaSign  = delta > 0 ? '+' : ''

  return (
    <div className="bg-surface border border-border p-5 mb-8 flex items-center justify-between gap-6 flex-wrap">
      <div>
        <p className="mono-label mb-2">Score Trend</p>
        <Sparkline data={last10} />
        <p className="font-mono text-[0.6rem] text-muted mt-2 tracking-wider">
          Last {last10.length} attempts
        </p>
      </div>
      <div className="text-right">
        <p className="mono-label mb-1">Latest</p>
        <p className="font-mono text-3xl font-semibold text-bright">{latest}%</p>
        {delta !== 0 && (
          <p className={`font-mono text-xs mt-0.5 ${deltaColor}`}>
            {deltaSign}{delta}% vs prev
          </p>
        )}
      </div>
    </div>
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { user } = useAuth()
  const [attempts, setAttempts]       = useState([])
  const [loading, setLoading]         = useState(true)
  const [examFilter, setExamFilter]   = useState('all')

  useEffect(() => {
    async function load() {
      const local = JSON.parse(localStorage.getItem('examprep_attempts') || '[]')

      if (user) {
        const remote = await fetchAttempts(user.uid)
        const merged = [...local]
        remote.forEach(r => {
          if (!merged.find(l => l.id === r.id)) merged.push(r)
        })
        merged.sort((a, b) => new Date(b.date) - new Date(a.date))
        setAttempts(merged)
      } else {
        setAttempts(local)
      }
      setLoading(false)
    }
    load()
  }, [user])

  // Filtered attempts based on active tab
  const filtered = useMemo(() => {
    if (examFilter === 'all') return attempts
    return attempts.filter(a => a.exam === examFilter)
  }, [attempts, examFilter])

  // Stats (computed on filtered set)
  const total     = filtered.length
  const avgScore  = total
    ? (filtered.reduce((s, a) => s + (a.score / a.maxScore) * 100, 0) / total).toFixed(1)
    : '—'
  const totalTime = filtered.reduce((s, a) => s + (a.timeTaken || 0), 0)
  const best      = total ? Math.max(...filtered.map(a => pct(a))) : '—'

  if (loading) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <span className="font-mono text-xs text-muted tracking-widest uppercase">Loading…</span>
      </div>
    )
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-start justify-between mb-8 border-b border-border pb-6">
        <div>
          <p className="font-mono text-xs tracking-widest uppercase text-muted mb-1">
            {user ? `Signed in as ${user.email}` : 'Local session — sign in to sync'}
          </p>
          <h1 className="font-display text-3xl font-bold text-bright tracking-tight">Dashboard</h1>
        </div>
        <Link to="/" className="btn btn-primary">New Test →</Link>
      </div>

      {/* Exam filter tabs */}
      <ExamTabs active={examFilter} onChange={setExamFilter} />

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border border border-border mb-8">
        {[
          { label: 'Tests Taken',  val: total },
          { label: 'Avg Score %',  val: avgScore },
          { label: 'Best Score %', val: best },
          { label: 'Total Time',   val: total ? fmtTime(totalTime) : '—' },
        ].map(s => (
          <div key={s.label} className="bg-surface p-5">
            <p className="font-mono text-2xl font-semibold text-bright tracking-tight mb-1">{s.val}</p>
            <p className="font-mono text-[0.65rem] tracking-widest uppercase text-muted">{s.label}</p>
          </div>
        ))}
      </div>

      {total === 0 ? (
        <div className="border border-dashed border-border2 py-20 text-center">
          <p className="font-mono text-3xl mb-3 opacity-20">📋</p>
          <p className="text-muted text-sm mb-4">
            {examFilter === 'all'
              ? 'No tests taken yet. Start your first mock test now.'
              : `No ${(EXAM_CONFIG[examFilter] || {}).name || examFilter} attempts yet.`}
          </p>
          <Link to="/" className="btn btn-primary">Pick an Exam →</Link>
        </div>
      ) : (
        <>
          {/* Per-exam breakdown (only when a specific exam tab is active) */}
          <ExamBreakdown attempts={filtered} examId={examFilter} />

          {/* Score trend sparkline */}
          <ScoreTrendCard attempts={filtered} />

          {/* Recent attempts table */}
          <p className="section-title">Recent Attempts</p>
          <table className="w-full border-collapse border border-border mb-2 text-sm">
            <thead>
              <tr className="bg-surface2">
                {['Exam', 'Date', 'Score', 'Accuracy', 'Mode', 'Time', ''].map(h => (
                  <th
                    key={h}
                    className="font-mono text-[0.65rem] tracking-widest uppercase text-muted text-left px-4 py-2.5 border-b border-border font-semibold"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 15).map(a => {
                const scorePct = pct(a)
                const cfg = EXAM_CONFIG[a.exam] || {}
                return (
                  <tr key={a.id} className="border-b border-border last:border-b-0 hover:bg-surface2 transition-colors">
                    <td className="px-4 py-3">
                      <span className="tag tag-grey">{cfg.name || a.exam}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">{fmtDate(a.date)}</td>
                    <td className="px-4 py-3 font-mono text-sm font-semibold text-bright">
                      {a.score.toFixed(2)}{' '}
                      <span className="text-muted font-normal">/ {a.maxScore}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-mono text-sm font-semibold ${
                          scorePct >= 60 ? 'text-correct' : scorePct >= 40 ? 'text-gold' : 'text-wrong'
                        }`}
                      >
                        {scorePct}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <ModeBadge mode={a.mode} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">{fmtTime(a.timeTaken || 0)}</td>
                    <td className="px-4 py-3 text-right">
                      {a.questions && (
                        <button
                          onClick={() => {
                            localStorage.setItem('examprep_lastAttempt', JSON.stringify(a))
                            window.location.href = '/solutions'
                          }}
                          className="btn btn-ghost btn-sm text-xs"
                        >
                          Solutions
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {filtered.length > 15 && (
            <p className="font-mono text-[0.65rem] text-muted tracking-wider mb-8 text-right">
              Showing 15 of {filtered.length} attempts
            </p>
          )}

          {/* Subject accuracy heatmap */}
          <SubjectHeatmap attempts={filtered} />
        </>
      )}

      {!user && (
        <div className="mt-8 bg-surface2 border border-border2 p-5 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm text-bright font-semibold mb-0.5">Sync progress across devices</p>
            <p className="text-xs text-muted">Sign in with Google to save your history to the cloud.</p>
          </div>
        </div>
      )}
    </main>
  )
}
