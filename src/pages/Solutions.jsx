import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { isBookmarked, toggleBookmark } from '../lib/bookmarks'

const FILTERS = ['All', 'Correct', 'Wrong', 'Skipped']
const LETTERS = ['A', 'B', 'C', 'D']

export default function Solutions() {
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(null)
  const [filter, setFilter]   = useState('All')

  useEffect(() => {
    const raw = localStorage.getItem('examprep_lastAttempt')
    if (!raw) { navigate('/'); return }
    setAttempt(JSON.parse(raw))
  }, [])

  if (!attempt) return null

  const { questions, answers, examName } = attempt

  const filtered = questions.map((q, i) => {
    const your = answers[i]
    const status =
      your == null ? 'Skipped' :
      your === q.correct ? 'Correct' : 'Wrong'
    return { q, i, your, status }
  }).filter(({ status }) => filter === 'All' || status === filter)

  const counts = {
    All:     questions.length,
    Correct: answers.filter((a, i) => a === questions[i].correct).length,
    Wrong:   answers.filter((a, i) => a != null && a !== questions[i].correct).length,
    Skipped: answers.filter(a => a == null).length,
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="font-mono text-xs tracking-widest uppercase text-muted mb-1">{examName}</p>
          <h1 className="font-display text-2xl font-bold text-bright tracking-tight">Solution Review</h1>
        </div>
        <Link to="/result" className="btn btn-ghost btn-sm">← Back to Result</Link>
      </div>

      {/* Filter tabs */}
      <div className="flex border border-border mb-6 w-fit">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={[
              'px-4 py-2 font-mono text-xs tracking-widest uppercase border-r border-border last:border-r-0 cursor-pointer transition-colors',
              filter === f
                ? 'bg-gold/10 text-gold'
                : 'bg-surface text-muted hover:text-ink hover:bg-surface2',
            ].join(' ')}
          >
            {f} <span className="opacity-60">({counts[f]})</span>
          </button>
        ))}
      </div>

      {/* Solution cards */}
      <div className="flex flex-col gap-px bg-border border border-border">
        {filtered.length === 0 && (
          <div className="bg-surface py-16 text-center">
            <p className="text-muted font-mono text-sm">No questions in this category.</p>
          </div>
        )}

        {filtered.map(({ q, i, your, status }) => (
          <div key={q.id} className="bg-surface p-6">
            {/* Card header */}
            <div className="flex items-center gap-3 mb-3">
              <span className="font-mono text-xs text-muted">Q{i + 1}</span>
              <span className="tag tag-grey">{q.subject}</span>
              <StatusBadge status={status} />
              <BookmarkButton questionId={q.id} question={q} exam={attempt.exam} />
            </div>

            {/* Question */}
            <p className="text-[0.95rem] text-bright leading-relaxed mb-4">{q.text}</p>

            {/* Options */}
            <div className="flex flex-col gap-1.5 mb-4">
              {q.options.map((opt, oi) => {
                const isCorrect  = oi === q.correct
                const isYours    = oi === your
                const isYourWrong = isYours && !isCorrect

                let cls = 'bg-transparent border-transparent text-muted'
                if (isCorrect)   cls = 'bg-correct/8 border-correct/30 text-correct'
                if (isYourWrong) cls = 'bg-wrong/8 border-wrong/30 text-wrong'

                let letterCls = 'bg-surface3 border-border text-muted'
                if (isCorrect)   letterCls = 'bg-correct/10 border-correct/30 text-correct'
                if (isYourWrong) letterCls = 'bg-wrong/10 border-wrong/30 text-wrong'

                return (
                  <div
                    key={oi}
                    className={`flex items-start gap-3 px-3 py-2.5 border text-sm leading-relaxed ${cls}`}
                  >
                    <span className={`shrink-0 font-mono text-xs w-5 h-5 flex items-center justify-center border mt-0.5 ${letterCls}`}>
                      {LETTERS[oi]}
                    </span>
                    <span className="flex-1">{opt}</span>
                    <span className="shrink-0 font-mono text-[0.65rem] self-center">
                      {isCorrect && '✓ Correct'}
                      {isYourWrong && '✗ Your answer'}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* Skipped indicator */}
            {your == null && (
              <p className="font-mono text-xs text-muted mb-3">— You skipped this question</p>
            )}

            {/* Explanation */}
            <div className="border-l-2 border-gold pl-4 py-0.5">
              <p className="font-mono text-[0.65rem] tracking-widest uppercase text-gold mb-1">Explanation</p>
              <p className="text-sm text-muted leading-relaxed">{q.explanation}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom nav */}
      <div className="mt-6 flex gap-3">
        <Link to="/result"    className="btn btn-outline">← Result</Link>
        <Link to="/dashboard" className="btn btn-ghost">Dashboard</Link>
        <Link to="/"          className="btn btn-ghost ml-auto">New Test →</Link>
      </div>
    </main>
  )
}

function StatusBadge({ status }) {
  const map = {
    Correct: 'tag tag-green',
    Wrong:   'tag tag-red',
    Skipped: 'tag tag-grey',
  }
  return <span className={map[status]}>{status}</span>
}

function BookmarkButton({ questionId, question, exam }) {
  const [saved, setSaved] = useState(() => isBookmarked(questionId))
  function toggle() {
    toggleBookmark(question, exam)
    setSaved(isBookmarked(questionId))
  }
  return (
    <button
      onClick={toggle}
      title={saved ? 'Remove bookmark' : 'Bookmark this question'}
      className={[
        'ml-auto font-mono text-xs border px-2 py-0.5 transition-colors cursor-pointer bg-transparent',
        saved
          ? 'border-[#e8a020]/40 text-[#e8a020] bg-[#e8a020]/8'
          : 'border-[#1a2d4a] text-[#5c7290] hover:border-[#244166] hover:text-[#dce5f0]',
      ].join(' ')}
    >
      {saved ? '★ Saved' : '☆ Save'}
    </button>
  )
}
