import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const EXAM_LABELS = { u: 'UPSC', a: 'APSC', c: 'CAT' }
const OPTION_LETTERS = ['A', 'B', 'C', 'D']

// ── Helpers ───────────────────────────────────────────────────────────────────

function getTodayStr() {
  return new Date().toISOString().slice(0, 10)
}

function formatDisplayDate(isoStr) {
  const [y, m, d] = isoStr.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function QuestionOfTheDay() {
  const today = getTodayStr()
  const [q, setQ]         = useState(null)
  const [examKey, setExamKey] = useState('UPSC')

  useEffect(() => {
    Promise.all([
      import('../data/upsc.json'),
      import('../data/apsc.json'),
      import('../data/cat.json'),
    ]).then(([u, a, c]) => {
      const all = [...u.default, ...a.default, ...c.default]
      const dayIdx = Math.floor(Date.now() / 86400000) % all.length
      const daily = all[dayIdx]
      setQ(daily)
      setExamKey(EXAM_LABELS[daily.id[0]] ?? 'UPSC')
    })
  }, [])

  const [state, setState] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('examprep_qotd') || 'null')
      if (saved?.date === today) return saved
    } catch (_) { /* ignore parse errors */ }
    return { date: today, answered: false, chosen: null, wasCorrect: null }
  })

  function handleAnswer(optIdx) {
    if (state.answered) return
    const wasCorrect = optIdx === q.correct
    const next = { date: today, answered: true, chosen: optIdx, wasCorrect }
    setState(next)
    localStorage.setItem('examprep_qotd', JSON.stringify(next))
  }

  if (!q) return (
    <div className="border border-border border-l-2 border-l-gold bg-surface p-6 flex items-center justify-center h-32">
      <span className="font-mono text-xs text-muted tracking-widest uppercase">Loading…</span>
    </div>
  )

  // ── Option styling ──────────────────────────────────────────────────────────

  function optionClasses(idx) {
    const base =
      'w-full text-left px-4 py-3 border rounded text-sm font-sans leading-snug transition-colors duration-150 flex items-start gap-3'

    if (!state.answered) {
      return `${base} border-border bg-surface2 text-ink hover:border-border2 hover:bg-surface cursor-pointer`
    }

    if (idx === q.correct) {
      return `${base} border-correct/30 bg-correct/10 text-correct pointer-events-none`
    }
    if (idx === state.chosen) {
      return `${base} border-wrong/30 bg-wrong/10 text-wrong pointer-events-none`
    }
    return `${base} border-border bg-surface2 text-muted pointer-events-none opacity-60`
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="border border-border border-l-2 border-l-gold bg-surface p-6 md:p-8">

      {/* Header row */}
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="w-5 h-px bg-gold" />
          <span className="font-mono text-[0.62rem] tracking-[0.22em] uppercase text-gold">
            Question of the Day
          </span>
        </div>

        {/* Meta tags */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[0.6rem] tracking-widest uppercase text-muted">
            {formatDisplayDate(today)}
          </span>
          <span className="w-px h-3 bg-border2 self-center" />
          <span className="tag tag-gold">{examKey}</span>
          {q.subject && (
            <span className="tag tag-grey">{q.subject}</span>
          )}
        </div>
      </div>

      {/* Question text */}
      <p className="font-display text-base md:text-lg text-bright leading-[1.65] mb-6">
        {q.text}
      </p>

      {/* Options */}
      <div className="flex flex-col gap-2.5 mb-6">
        {q.options.map((opt, idx) => (
          <button
            key={idx}
            className={optionClasses(idx)}
            onClick={() => handleAnswer(idx)}
            disabled={state.answered}
            aria-label={`Option ${OPTION_LETTERS[idx]}: ${opt}`}
          >
            <span className="font-mono text-[0.68rem] tracking-widest uppercase shrink-0 mt-0.5 opacity-70">
              {OPTION_LETTERS[idx]}.
            </span>
            <span>{opt}</span>

            {/* Result icon — only after answering */}
            {state.answered && idx === q.correct && (
              <span className="ml-auto shrink-0 text-correct font-bold text-base leading-none self-center">
                ✓
              </span>
            )}
            {state.answered && idx === state.chosen && idx !== q.correct && (
              <span className="ml-auto shrink-0 text-wrong font-bold text-base leading-none self-center">
                ✗
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Post-answer block */}
      {state.answered && (
        <div className="flex flex-col gap-4">

          {/* Result line */}
          <div className="flex items-center gap-3">
            {state.wasCorrect ? (
              <>
                <span className="font-mono text-[0.65rem] tracking-[0.18em] uppercase text-correct font-semibold">
                  Correct!
                </span>
                <span className="font-mono text-[0.65rem] tracking-[0.15em] uppercase text-muted">
                  +2 pts
                </span>
              </>
            ) : (
              <>
                <span className="font-mono text-[0.65rem] tracking-[0.18em] uppercase text-wrong font-semibold">
                  Incorrect.
                </span>
                <span className="font-mono text-[0.65rem] tracking-[0.15em] uppercase text-muted">
                  The answer was {OPTION_LETTERS[q.correct]}.
                </span>
              </>
            )}
          </div>

          {/* Explanation */}
          {q.explanation && (
            <div className="border-l-2 border-gold pl-3">
              <p className="text-sm text-muted leading-relaxed">{q.explanation}</p>
            </div>
          )}

          {/* Link to tests */}
          <div>
            <Link
              to="/tests"
              className="font-mono text-[0.65rem] tracking-[0.15em] uppercase text-gold hover:text-bright transition-colors duration-150"
            >
              View in context →
            </Link>
          </div>

        </div>
      )}

    </div>
  )
}
