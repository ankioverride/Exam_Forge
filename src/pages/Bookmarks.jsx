import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getBookmarks, removeBookmark } from '../lib/bookmarks'

const LETTERS = ['A', 'B', 'C', 'D']
const EXAM_FILTERS = ['All', 'UPSC', 'APSC', 'CAT']

export default function Bookmarks() {
  const [bookmarks, setBookmarks]   = useState([])
  const [examFilter, setExamFilter] = useState('all')
  const [subjectFilter, setSubjectFilter] = useState('all')
  const [showExp, setShowExp]       = useState({})   // { questionId: bool }

  useEffect(() => {
    setBookmarks(getBookmarks())
  }, [])

  function refresh() {
    setBookmarks(getBookmarks())
  }

  function handleRemove(id) {
    removeBookmark(id)
    refresh()
  }

  function handleClearAll() {
    if (window.confirm('Remove all bookmarks? This cannot be undone.')) {
      // clear directly then refresh
      localStorage.removeItem('examprep_bookmarks')
      refresh()
    }
  }

  function toggleExp(id) {
    setShowExp(prev => ({ ...prev, [id]: !prev[id] }))
  }

  // derive subject list from current full bookmarks (not filtered)
  const subjects = ['all', ...Array.from(new Set(bookmarks.map(b => b.subject).filter(Boolean)))]

  const filtered = bookmarks.filter(b => {
    const examMatch    = examFilter === 'all' || b.exam === examFilter
    const subjectMatch = subjectFilter === 'all' || b.subject === subjectFilter
    return examMatch && subjectMatch
  })

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-2xl font-bold text-bright tracking-tight">Bookmarks</h1>
          <span className="font-mono text-xs bg-gold/10 text-gold border border-gold/30 px-2 py-0.5">
            {bookmarks.length}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {bookmarks.length > 0 && (
            <button
              onClick={handleClearAll}
              className="btn btn-ghost btn-sm text-wrong hover:text-wrong hover:border-wrong/40"
            >
              Clear All
            </button>
          )}
          <Link to="/dashboard" className="btn btn-ghost btn-sm">← Dashboard</Link>
        </div>
      </div>

      {/* Exam filter tabs */}
      <div className="flex border border-border mb-4 w-fit">
        {EXAM_FILTERS.map(f => {
          const val = f.toLowerCase()
          return (
            <button
              key={f}
              onClick={() => setExamFilter(val)}
              className={[
                'px-4 py-2 font-mono text-xs tracking-widest uppercase border-r border-border last:border-r-0 cursor-pointer transition-colors',
                examFilter === val
                  ? 'bg-gold/10 text-gold'
                  : 'bg-surface text-muted hover:text-ink hover:bg-surface2',
              ].join(' ')}
            >
              {f}
            </button>
          )
        })}
      </div>

      {/* Subject filter dropdown */}
      {subjects.length > 2 && (
        <div className="mb-6">
          <select
            value={subjectFilter}
            onChange={e => setSubjectFilter(e.target.value)}
            className="font-mono text-xs bg-surface border border-border text-ink px-3 py-2 focus:outline-none focus:border-border2 cursor-pointer"
          >
            {subjects.map(s => (
              <option key={s} value={s}>
                {s === 'all' ? 'All subjects' : s}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Empty state */}
      {bookmarks.length === 0 ? (
        <div className="border border-border bg-surface py-20 text-center">
          <p className="font-mono text-xs tracking-widest uppercase text-muted mb-2">★</p>
          <p className="text-ink text-sm mb-1">No bookmarks yet.</p>
          <p className="text-muted text-sm">Star questions in the solution review to save them here.</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="border border-border bg-surface py-16 text-center">
          <p className="text-muted font-mono text-sm">No bookmarks match this filter.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-px bg-border border border-border">
          {filtered.map(b => (
            <div key={b.id} className="bg-surface p-6">
              {/* Card header */}
              <div className="flex items-start gap-3 mb-3">
                {b.exam && (
                  <span className="tag tag-gold shrink-0">{b.exam}</span>
                )}
                {b.subject && (
                  <span className="tag tag-grey shrink-0">{b.subject}</span>
                )}
                <button
                  onClick={() => handleRemove(b.id)}
                  title="Remove bookmark"
                  className="ml-auto shrink-0 font-mono text-xs border border-border text-muted hover:border-wrong/40 hover:text-wrong px-2 py-0.5 bg-transparent transition-colors cursor-pointer"
                >
                  ✕ Remove
                </button>
              </div>

              {/* Question text */}
              <p className="text-[0.95rem] text-bright leading-relaxed mb-4">{b.text}</p>

              {/* Options */}
              <div className="flex flex-col gap-1.5 mb-4">
                {b.options.map((opt, oi) => {
                  const isCorrect = oi === b.correct

                  const cls = isCorrect
                    ? 'bg-correct/8 border-correct/30 text-correct'
                    : 'bg-transparent border-transparent text-muted'

                  const letterCls = isCorrect
                    ? 'bg-correct/10 border-correct/30 text-correct'
                    : 'bg-surface3 border-border text-muted'

                  return (
                    <div
                      key={oi}
                      className={`flex items-start gap-3 px-3 py-2.5 border text-sm leading-relaxed ${cls}`}
                    >
                      <span className={`shrink-0 font-mono text-xs w-5 h-5 flex items-center justify-center border mt-0.5 ${letterCls}`}>
                        {LETTERS[oi]}
                      </span>
                      <span className="flex-1">{opt}</span>
                      {isCorrect && (
                        <span className="shrink-0 font-mono text-[0.65rem] self-center text-correct">
                          ✓ Correct
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Explanation toggle */}
              {b.explanation && (
                <div>
                  <button
                    onClick={() => toggleExp(b.id)}
                    className="font-mono text-xs text-gold hover:text-bright transition-colors cursor-pointer bg-transparent border-none p-0 mb-2"
                  >
                    {showExp[b.id] ? 'Hide Explanation ▲' : 'Show Explanation ▼'}
                  </button>
                  {showExp[b.id] && (
                    <div className="border-l-2 border-gold pl-4 py-0.5">
                      <p className="font-mono text-[0.65rem] tracking-widest uppercase text-gold mb-1">Explanation</p>
                      <p className="text-sm text-muted leading-relaxed">{b.explanation}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Saved date */}
              {b.savedAt && (
                <p className="font-mono text-[0.6rem] text-muted/50 mt-3">
                  Saved {new Date(b.savedAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Bottom nav */}
      <div className="mt-6 flex gap-3">
        <Link to="/dashboard" className="btn btn-outline">← Dashboard</Link>
        <Link to="/" className="btn btn-ghost ml-auto">New Test →</Link>
      </div>
    </main>
  )
}
