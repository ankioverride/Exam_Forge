import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { saveAttempt } from '../lib/auth'
import { loadQuestions, EXAM_CONFIG } from '../data/questions'

const STORAGE_KEY = 'examprep_activeTest'

function fmt(secs) {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function calcScore(questions, answers, exam) {
  const cfg = EXAM_CONFIG[exam]
  let score = 0, correct = 0, wrong = 0, skipped = 0
  questions.forEach((q, i) => {
    if (answers[i] == null) { skipped++; return }
    if (answers[i] === q.correct) { score += cfg.correctMarks; correct++ }
    else { score -= cfg.negativeMarks; wrong++ }
  })
  return { score: Math.max(0, parseFloat(score.toFixed(2))), correct, wrong, skipped }
}

export default function Test() {
  const { exam }          = useParams()
  const navigate          = useNavigate()
  const { user }          = useAuth()
  const config            = EXAM_CONFIG[exam]
  const [searchParams]    = useSearchParams()

  // Parse opts from search params
  const mode       = searchParams.get('mode') || 'timed'
  const subjects   = searchParams.get('subjects')?.split(',').filter(Boolean) || []
  const count      = parseInt(searchParams.get('count')) || undefined
  const difficulty = searchParams.get('difficulty') || undefined

  // ── State ──────────────────────────────────────────────────────
  const [allQ, setAllQ]           = useState([])
  const [loading, setLoading]     = useState(true)
  const [idx, setIdx]             = useState(0)
  const [answers, setAnswers]     = useState([])
  const [visited, setVisited]     = useState(() => new Set([0]))
  const [timeLeft, setTimeLeft]   = useState(config?.timeMinutes * 60 ?? 1200)
  const [submitted, setSubmitted] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [revealed, setRevealed]   = useState({})
  const timerRef = useRef(null)

  // Load questions asynchronously
  useEffect(() => {
    if (!config) return
    loadQuestions(exam, { subjects, count, difficulty }).then(qs => {
      setAllQ(qs)
      setAnswers(Array(qs.length).fill(null))
      setLoading(false)
    })
  }, [exam])

  // Restore from localStorage if navigating back mid-test
  useEffect(() => {
    if (loading) return
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const s = JSON.parse(saved)
        if (s.exam === exam && s.mode === mode) {
          setAnswers(s.answers)
          setTimeLeft(s.timeLeft)
          setIdx(s.idx ?? 0)
          setVisited(new Set(s.visited ?? [0]))
        }
      } catch { /* ignore */ }
    }
  }, [loading, exam])

  // Timer — only in timed mode
  useEffect(() => {
    if (submitted || mode === 'practice' || loading) return
    timerRef.current = setInterval(() => setTimeLeft(t => t - 1), 1000)
    return () => clearInterval(timerRef.current)
  }, [submitted, mode, loading])

  // Auto-submit on time up (timed mode only)
  useEffect(() => {
    if (timeLeft <= 0 && !submitted && mode !== 'practice') doSubmit()
  }, [timeLeft])

  // Persist to localStorage
  useEffect(() => {
    if (submitted || loading) return
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ exam, mode, answers, timeLeft, idx, visited: [...visited] }))
  }, [answers, timeLeft, idx])

  // Auth guard — redirect to home if not signed in
  if (!user) {
    navigate('/')
    return null
  }

  // Invalid exam
  if (!config) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <p className="text-muted font-mono text-sm">Unknown exam. <a href="/" className="text-gold">Go home</a></p>
      </div>
    )
  }

  // Loading skeleton
  if (loading) {
    return (
      <div className="flex flex-col" style={{ height: 'calc(100vh - 56px)' }}>
        <div className="bg-surface border-b border-border h-12 flex items-center gap-4 px-6 shrink-0">
          <span className="font-display text-base font-bold text-bright tracking-tight shrink-0">
            Exam<span className="text-gold">Forge</span>
          </span>
          <span className="text-dim font-mono text-xs">|</span>
          <span className="font-mono text-xs font-semibold tracking-widest uppercase text-ink">{config.name}</span>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="w-8 h-8 border-2 border-gold border-t-transparent rounded-full animate-spin" />
            <p className="font-mono text-xs text-muted tracking-widest uppercase">Loading questions…</p>
          </div>
        </div>
      </div>
    )
  }

  // No questions found after filtering
  if (allQ.length === 0) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <p className="text-muted font-mono text-sm">No questions match your filters. <a href="/" className="text-gold">Go home</a></p>
      </div>
    )
  }

  const q = allQ[idx]

  function selectAnswer(optIdx) {
    if (submitted) return
    setAnswers(prev => { const a = [...prev]; a[idx] = optIdx; return a })
    if (mode === 'practice' && optIdx != null) {
      setRevealed(r => ({ ...r, [idx]: true }))
    }
  }

  function goTo(i) {
    setIdx(i)
    setVisited(v => new Set([...v, i]))
  }

  function doSubmit() {
    clearInterval(timerRef.current)
    setSubmitted(true)

    const stats = calcScore(allQ, answers, exam)

    // Subject breakdown
    const subjectBreakdown = {}
    allQ.forEach((q, i) => {
      if (!subjectBreakdown[q.subject]) subjectBreakdown[q.subject] = { correct: 0, total: 0 }
      subjectBreakdown[q.subject].total++
      if (answers[i] === q.correct) subjectBreakdown[q.subject].correct++
    })

    const attempt = {
      id:               Date.now(),
      exam,
      examName:         config.name,
      mode,
      date:             new Date().toISOString(),
      score:            stats.score,
      maxScore:         allQ.length * config.correctMarks,
      correct:          stats.correct,
      wrong:            stats.wrong,
      skipped:          stats.skipped,
      timeTaken:        config.timeMinutes * 60 - timeLeft,
      questions:        allQ,
      answers,
      subjectBreakdown,
    }

    // Save attempt for result/solutions pages
    localStorage.setItem('examprep_lastAttempt', JSON.stringify(attempt))

    // Append to history
    const hist = JSON.parse(localStorage.getItem('examprep_attempts') || '[]')
    localStorage.setItem('examprep_attempts', JSON.stringify([attempt, ...hist].slice(0, 50)))

    // Clear active test
    localStorage.removeItem(STORAGE_KEY)

    // Sync to Firestore if logged in
    if (user) saveAttempt(user.uid, attempt)

    navigate('/result')
  }

  const timerColor = timeLeft <= 60
    ? 'text-wrong'
    : timeLeft <= 180
    ? 'text-gold'
    : 'text-bright'

  const LETTERS = ['A', 'B', 'C', 'D']
  const isPractice = mode === 'practice'

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 56px)' }}>
      {/* Top bar */}
      <div className="bg-surface border-b border-border h-12 flex items-center gap-4 px-6 shrink-0">
        {/* Logo */}
        <span className="font-display text-base font-bold text-bright tracking-tight shrink-0">
          Exam<span className="text-gold">Forge</span>
        </span>
        <span className="text-dim font-mono text-xs">|</span>
        <span className="font-mono text-xs font-semibold tracking-widest uppercase text-ink">{config.name}</span>
        {/* Mode tag */}
        <span className={`tag font-mono text-[0.6rem] tracking-widest uppercase px-2 py-0.5 ${isPractice ? 'tag-green' : 'tag-gold'}`}>
          {isPractice ? 'Practice' : 'Timed'}
        </span>
        <span className="text-dim font-mono text-xs hidden md:block">·</span>
        <span className="font-mono text-xs text-muted hidden md:block">{q.subject}</span>
        <span className="font-mono text-xs text-gold ml-auto">Q {idx + 1} / {allQ.length}</span>
        <button
          onClick={() => { if (window.confirm('Exit test? Your progress will be lost.')) navigate('/') }}
          className="font-mono text-[0.65rem] tracking-widest uppercase text-muted hover:text-wrong border border-border hover:border-wrong/40 px-2.5 py-1 bg-transparent cursor-pointer transition-colors ml-2"
        >
          Exit
        </button>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Question panel ── */}
        <div className="flex-1 overflow-y-auto p-8 border-r border-border">
          {/* Question */}
          <div className="flex items-start gap-3 mb-6">
            <span className="shrink-0 font-mono text-xs bg-gold/10 text-gold border border-gold/25 px-2 py-0.5 mt-0.5">
              Q{idx + 1}
            </span>
            <p className="text-[1.05rem] text-bright leading-relaxed font-sans">{q.text}</p>
          </div>

          {/* Options */}
          <div className="flex flex-col gap-2.5 mb-8">
            {q.options.map((opt, oi) => {
              const chosen  = answers[idx] === oi
              const isReveal = isPractice && revealed[idx]
              const isCorrect = oi === q.correct
              const isWrong   = chosen && !isCorrect

              let optClass = 'bg-surface2 border-border hover:border-border2 hover:bg-surface3 text-ink'
              let badgeClass = 'bg-surface3 border-border2 text-muted'

              if (isReveal) {
                if (isCorrect) {
                  optClass   = 'bg-correct/10 border-correct/40 text-bright'
                  badgeClass = 'bg-correct text-black border-correct'
                } else if (isWrong) {
                  optClass   = 'bg-wrong/10 border-wrong/40 text-bright'
                  badgeClass = 'bg-wrong text-black border-wrong'
                } else {
                  optClass   = 'bg-surface2 border-border text-ink opacity-60'
                  badgeClass = 'bg-surface3 border-border2 text-muted'
                }
              } else if (chosen) {
                optClass   = 'bg-gold/10 border-gold/40 text-bright'
                badgeClass = 'bg-gold text-black border-gold'
              }

              return (
                <button
                  key={oi}
                  onClick={() => selectAnswer(oi)}
                  disabled={isReveal}
                  className={[
                    'flex items-start gap-3 px-4 py-3.5 text-left w-full transition-all duration-100 border font-sans text-sm leading-relaxed',
                    isReveal ? 'cursor-default' : 'cursor-pointer',
                    optClass,
                  ].join(' ')}
                >
                  <span className={[
                    'shrink-0 font-mono text-xs w-[22px] h-[22px] flex items-center justify-center border mt-0.5 transition-all',
                    badgeClass,
                  ].join(' ')}>
                    {LETTERS[oi]}
                  </span>
                  {opt}
                </button>
              )
            })}
          </div>

          {/* Practice mode explanation reveal */}
          {isPractice && revealed[idx] && (
            <div className="border-l-2 border-gold pl-4 mt-4 mb-8">
              <p className="font-mono text-[0.65rem] uppercase text-gold tracking-widest mb-1">Explanation</p>
              <p className="text-sm text-muted">{q.explanation}</p>
            </div>
          )}

          {/* Navigation */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => goTo(Math.max(0, idx - 1))}
              disabled={idx === 0}
              className="btn btn-outline btn-sm disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ← Prev
            </button>
            <button
              onClick={() => { selectAnswer(null); goTo(idx) }}
              className="btn btn-ghost btn-sm text-muted"
              title="Clear answer and mark as skipped"
            >
              Clear
            </button>
            <button
              onClick={() => goTo(Math.min(allQ.length - 1, idx + 1))}
              disabled={idx === allQ.length - 1}
              className="btn btn-outline btn-sm disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next →
            </button>
            <button
              onClick={() => setShowConfirm(true)}
              className="btn btn-primary btn-sm ml-auto"
            >
              Submit Test
            </button>
          </div>
        </div>

        {/* ── Sidebar ── */}
        <div className="w-[240px] shrink-0 flex flex-col gap-4 p-4 overflow-y-auto bg-surface">
          {/* Timer (timed mode) or Practice label */}
          {isPractice ? (
            <div className="bg-surface2 border border-border p-3 text-center">
              <p className="font-mono text-[0.6rem] tracking-[0.15em] uppercase text-muted mb-1">Mode</p>
              <p className="font-mono text-sm font-semibold text-correct tracking-widest uppercase">Practice</p>
              <p className="font-mono text-[0.58rem] text-muted mt-1">No time limit · answers revealed on select</p>
            </div>
          ) : (
            <div className="bg-surface2 border border-border p-3 text-center">
              <p className="font-mono text-[0.6rem] tracking-[0.15em] uppercase text-muted mb-1">Time Remaining</p>
              <p className={`font-mono text-[2rem] font-semibold leading-none tracking-tight ${timerColor} ${timeLeft <= 60 ? 'animate-pulse' : ''}`}>
                {fmt(timeLeft)}
              </p>
            </div>
          )}

          {/* Question grid */}
          <div>
            <p className="font-mono text-[0.6rem] tracking-[0.15em] uppercase text-muted mb-2">Questions</p>
            <div className="grid grid-cols-5 gap-1">
              {allQ.map((_, i) => {
                const isCurrent  = i === idx
                const isAnswered = answers[i] != null
                const isVisited  = visited.has(i)

                return (
                  <button
                    key={i}
                    onClick={() => goTo(i)}
                    className={[
                      'aspect-square flex items-center justify-center font-mono text-[0.7rem] font-semibold border transition-all cursor-pointer',
                      isCurrent  ? 'bg-gold text-black border-gold' :
                      isAnswered ? 'bg-gold/10 border-gold/30 text-gold' :
                      isVisited  ? 'bg-surface3 border-border2 text-muted' :
                                   'bg-surface2 border-border text-dim',
                    ].join(' ')}
                  >
                    {i + 1}
                  </button>
                )
              })}
            </div>

            {/* Legend */}
            <div className="mt-3 flex flex-col gap-1.5">
              {[
                { cls: 'bg-gold',      label: 'Current' },
                { cls: 'bg-gold/10 border border-gold/30', label: 'Answered' },
                { cls: 'bg-surface3 border border-border2', label: 'Visited' },
                { cls: 'bg-surface2 border border-border', label: 'Not seen' },
              ].map(l => (
                <div key={l.label} className="flex items-center gap-2">
                  <span className={`w-3 h-3 shrink-0 ${l.cls}`} />
                  <span className="font-mono text-[0.65rem] text-muted">{l.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Stats */}
          <div className="bg-surface2 border border-border p-3 mt-auto">
            <div className="grid grid-cols-3 gap-1 text-center">
              <div>
                <p className="font-mono text-sm font-semibold text-correct">{answers.filter(a => a != null).length}</p>
                <p className="font-mono text-[0.58rem] text-muted uppercase tracking-widest">Done</p>
              </div>
              <div>
                <p className="font-mono text-sm font-semibold text-muted">{answers.filter(a => a == null).length}</p>
                <p className="font-mono text-[0.58rem] text-muted uppercase tracking-widest">Left</p>
              </div>
              <div>
                <p className="font-mono text-sm font-semibold text-ink">{allQ.length}</p>
                <p className="font-mono text-[0.58rem] text-muted uppercase tracking-widest">Total</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Confirm submit modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-bg/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-border2 p-8 max-w-sm w-full">
            <h2 className="font-display text-xl text-bright font-bold mb-2">Submit Test?</h2>
            <p className="text-sm text-muted mb-1">
              Answered: <span className="text-ink font-semibold">{answers.filter(a => a != null).length}</span> of {allQ.length}
            </p>
            <p className="text-sm text-muted mb-6">
              Skipped: <span className="text-wrong font-semibold">{answers.filter(a => a == null).length}</span> questions.
            </p>
            {!isPractice && (
              <p className="text-xs text-muted mb-6 border-l-2 border-gold pl-3">
                Skipped questions score 0. Wrong answers have negative marking ({EXAM_CONFIG[exam].negativeMarks} marks deducted).
              </p>
            )}
            <div className="flex gap-3">
              <button onClick={() => setShowConfirm(false)} className="btn btn-outline flex-1">Cancel</button>
              <button onClick={doSubmit} className="btn btn-primary flex-1">Submit →</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
