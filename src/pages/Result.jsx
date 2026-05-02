import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { EXAM_CONFIG } from '../data/questions'

function fmt(secs) {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}m ${s}s`
}

function groupBySubject(questions, answers) {
  const map = {}
  questions.forEach((q, i) => {
    if (!map[q.subject]) map[q.subject] = { correct: 0, total: 0 }
    map[q.subject].total++
    if (answers[i] === q.correct) map[q.subject].correct++
  })
  return Object.entries(map).map(([name, v]) => ({
    name,
    correct: v.correct,
    total: v.total,
    pct: Math.round((v.correct / v.total) * 100),
  }))
}

export default function Result() {
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(null)

  useEffect(() => {
    const raw = localStorage.getItem('examprep_lastAttempt')
    if (!raw) { navigate('/'); return }
    setAttempt(JSON.parse(raw))
  }, [])

  if (!attempt) return null

  const { exam, examName, score, maxScore, correct, wrong, skipped, timeTaken, questions, answers } = attempt
  const accuracy = correct + wrong > 0 ? Math.round((correct / (correct + wrong)) * 100) : 0
  const subjects = groupBySubject(questions, answers)
  const cfg = EXAM_CONFIG[exam]

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      {/* Hero row */}
      <div className="border-b border-border pb-8 mb-8">
        <p className="font-mono text-xs tracking-widest uppercase text-muted mb-2">{examName} · Result</p>

        <div className="flex items-baseline gap-1.5 mb-1">
          <span className="font-mono text-6xl font-semibold text-bright tracking-tight leading-none">
            {score.toFixed(2)}
          </span>
          <span className="font-mono text-2xl text-muted">/ {maxScore}</span>
        </div>
        <p className="font-mono text-xs tracking-widest uppercase text-muted">Total Score</p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 border border-border mb-8">
        {[
          { label: 'Accuracy',  val: `${accuracy}%`,    cls: '' },
          { label: 'Correct',   val: correct,            cls: 'text-correct' },
          { label: 'Wrong',     val: wrong,              cls: 'text-wrong' },
          { label: 'Skipped',   val: skipped,            cls: 'text-muted' },
        ].map((s, i) => (
          <div
            key={s.label}
            className={`p-5 bg-surface border-r border-border last:border-r-0 ${i >= 2 ? 'border-t md:border-t-0' : ''}`}
          >
            <p className={`font-mono text-2xl font-semibold mb-1 ${s.cls || 'text-bright'}`}>{s.val}</p>
            <p className="font-mono text-[0.65rem] tracking-widest uppercase text-muted">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Time + marking */}
      <div className="grid grid-cols-2 gap-px bg-border border border-border mb-8">
        <div className="bg-surface p-4">
          <p className="font-mono text-xs tracking-widest uppercase text-muted mb-1">Time Taken</p>
          <p className="font-mono text-base font-semibold text-bright">{fmt(timeTaken)}</p>
        </div>
        <div className="bg-surface p-4">
          <p className="font-mono text-xs tracking-widest uppercase text-muted mb-1">Marking Scheme</p>
          <p className="font-mono text-base font-semibold text-bright">
            +{cfg.correctMarks} / −{cfg.negativeMarks}
          </p>
        </div>
      </div>

      {/* Subject breakdown */}
      <p className="section-title">Subject-wise Performance</p>
      <div className="flex flex-col gap-3 mb-8">
        {subjects.map(s => (
          <div key={s.name} className="grid items-center gap-4" style={{ gridTemplateColumns: '160px 1fr 48px' }}>
            <span className="font-mono text-xs text-muted truncate">{s.name}</span>
            <div className="h-1.5 bg-surface3 border border-border relative">
              <div
                className="h-full bg-gold transition-all duration-700"
                style={{ width: `${s.pct}%` }}
              />
            </div>
            <span className="font-mono text-xs text-muted text-right">{s.pct}%</span>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-3 flex-wrap">
        <Link to="/solutions" className="btn btn-primary btn-lg">
          View Solutions →
        </Link>
        <Link to="/dashboard" className="btn btn-outline btn-lg">
          Dashboard
        </Link>
        <Link to="/" className="btn btn-ghost btn-lg">
          Take Another Test
        </Link>
      </div>
    </main>
  )
}
