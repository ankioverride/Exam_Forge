import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { loadQuestions, EXAM_CONFIG } from '../data/questions'
import { useAuth } from '../lib/auth'

// ── Count options ────────────────────────────────────────────────────────────
const COUNT_OPTIONS = [10, 15, 20, 'All']

// ── Difficulty options ───────────────────────────────────────────────────────
const DIFFICULTY_OPTIONS = [
  { value: 'any',    label: 'Any' },
  { value: 'easy',   label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard',   label: 'Hard' },
]

export default function Configure() {
  const { exam }   = useParams()
  const navigate   = useNavigate()
  const { user }   = useAuth()

  // Auth guard
  if (!user) {
    navigate('/')
    return null
  }

  const config = EXAM_CONFIG[exam]

  const [mode,        setMode]       = useState(null)        // 'timed' | 'practice'
  const [count,       setCount]      = useState(10)
  const [subjects,    setSubjects]   = useState([])          // [] = all
  const [difficulty,  setDifficulty] = useState('any')
  const [allQuestions, setAllQuestions] = useState([])
  const [loadingQ,    setLoadingQ]   = useState(true)

  // ── Load questions on mount ──────────────────────────────────────────────
  useEffect(() => {
    if (!config) return
    loadQuestions(exam, {}).then(qs => {
      setAllQuestions(qs)
      setLoadingQ(false)
    })
  }, [exam])

  // ── Derived ──────────────────────────────────────────────────────────────
  const uniqueSubjects = loadingQ
    ? []
    : [...new Set(allQuestions.map(q => q.subject))].sort()

  // Count per subject
  const subjectCounts = uniqueSubjects.reduce((acc, s) => {
    acc[s] = allQuestions.filter(q => q.subject === s).length
    return acc
  }, {})

  // Total questions in the bank (respects subject + difficulty filter)
  const filteredPool = allQuestions.filter(q => {
    const subjectMatch    = subjects.length === 0 || subjects.includes(q.subject)
    const difficultyMatch = difficulty === 'any' || (q.difficulty ?? 'medium') === difficulty
    return subjectMatch && difficultyMatch
  })

  const bankTotal = filteredPool.length

  // Resolve numeric count (handle 'All')
  const resolvedCount = count === 'All' ? bankTotal : count

  // Whether a count option is disabled (bank doesn't have enough)
  function isCountDisabled(opt) {
    if (opt === 'All') return bankTotal === 0
    return bankTotal < opt
  }

  // Subject toggle
  function toggleSubject(subj) {
    setSubjects(prev =>
      prev.includes(subj) ? prev.filter(s => s !== subj) : [...prev, subj]
    )
  }

  // ── Summary text ─────────────────────────────────────────────────────────
  const summaryCount = count === 'All' ? bankTotal : Math.min(resolvedCount, bankTotal)
  const summaryMode  = mode === 'timed'    ? 'Timed'
                     : mode === 'practice' ? 'Practice'
                     : '—'
  const summarySubj  = subjects.length === 0
    ? 'all subjects'
    : subjects.length === 1
    ? subjects[0]
    : `${subjects.length} subjects`
  const summaryDiff  = difficulty === 'any' ? '' : ` · ${difficulty}`

  // ── Navigate on start ────────────────────────────────────────────────────
  function handleStart() {
    if (!mode) return
    const params = new URLSearchParams()
    params.set('mode', mode)
    params.set('count', count === 'All' ? bankTotal : count)
    if (subjects.length) params.set('subjects', subjects.join(','))
    if (difficulty !== 'any') params.set('difficulty', difficulty)
    navigate(`/test/${exam}?${params.toString()}`)
  }

  // ── Invalid exam guard ───────────────────────────────────────────────────
  if (!config) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <p className="text-muted font-mono text-sm">
          Unknown exam.{' '}
          <Link to="/tests" className="text-gold hover:underline">Back to tests</Link>
        </p>
      </div>
    )
  }

  return (
    <main className="max-w-2xl mx-auto px-6 py-12">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="mb-10">
        <Link
          to="/tests"
          className="inline-flex items-center gap-1.5 font-mono text-[0.7rem] tracking-[0.15em] uppercase text-muted hover:text-gold transition-colors mb-5"
        >
          <span>←</span> Back to tests
        </Link>

        <div className="flex items-center gap-2 font-mono text-[0.7rem] tracking-[0.18em] uppercase text-gold mb-3">
          <span className="w-6 h-px bg-gold inline-block" />
          {config.name}
        </div>

        <h1 className="font-display text-3xl lg:text-4xl font-bold text-bright tracking-tight leading-tight">
          Configure Your Test
        </h1>
        <p className="text-muted text-sm mt-2 leading-relaxed">
          Customise the session then hit Start — your choices are locked in once the clock begins.
        </p>
      </div>

      <div className="flex flex-col gap-6">

        {/* ── Mode picker ──────────────────────────────────────────── */}
        <Section label="Mode" required>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <ModeCard
              active={mode === 'timed'}
              onClick={() => setMode('timed')}
              title="Timed Test"
              icon={<ClockIcon />}
              description="Countdown timer · Auto-submit · Negative marking applies"
            />
            <ModeCard
              active={mode === 'practice'}
              onClick={() => setMode('practice')}
              title="Practice Mode"
              icon={<BookIcon />}
              description="No timer · See answer & explanation after each question"
            />
          </div>
        </Section>

        {/* ── Question count ───────────────────────────────────────── */}
        <Section label="Number of Questions" required>
          {loadingQ ? (
            <p className="font-mono text-xs text-muted">Loading question bank…</p>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {COUNT_OPTIONS.map(opt => {
                const disabled = isCountDisabled(opt)
                const active   = count === opt
                return (
                  <button
                    key={opt}
                    disabled={disabled}
                    onClick={() => !disabled && setCount(opt)}
                    className={[
                      'font-mono text-sm px-4 py-2 border transition-all',
                      disabled
                        ? 'border-border bg-surface2 text-dim cursor-not-allowed opacity-40'
                        : active
                        ? 'border-gold bg-gold/10 text-gold cursor-pointer'
                        : 'border-border2 bg-surface2 text-ink hover:border-gold/40 hover:bg-surface3 cursor-pointer',
                    ].join(' ')}
                  >
                    {opt === 'All' ? `All (${bankTotal})` : opt}
                  </button>
                )
              })}
            </div>
          )}
          {!loadingQ && bankTotal === 0 && subjects.length > 0 && (
            <p className="text-xs text-wrong font-mono mt-2">
              No questions match the current subject + difficulty combination.
            </p>
          )}
        </Section>

        {/* ── Subject filter ───────────────────────────────────────── */}
        <Section label="Subject Filter" hint="Optional — leave all unchecked to include every subject">
          {loadingQ ? (
            <p className="font-mono text-xs text-muted">Loading subjects…</p>
          ) : uniqueSubjects.length === 0 ? (
            <p className="font-mono text-xs text-muted">No subjects found.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {uniqueSubjects.map(subj => {
                const checked = subjects.includes(subj)
                return (
                  <label
                    key={subj}
                    className={[
                      'flex items-center gap-3 px-3.5 py-2.5 border cursor-pointer transition-all select-none',
                      checked
                        ? 'border-gold/40 bg-gold/8 text-ink'
                        : 'border-border bg-surface2 text-muted hover:border-border2 hover:bg-surface3',
                    ].join(' ')}
                  >
                    {/* Custom checkbox */}
                    <span
                      className={[
                        'w-4 h-4 shrink-0 border flex items-center justify-center transition-all',
                        checked
                          ? 'bg-gold border-gold'
                          : 'bg-surface3 border-border2',
                      ].join(' ')}
                    >
                      {checked && (
                        <svg width="10" height="8" viewBox="0 0 10 8" fill="none" aria-hidden="true">
                          <path d="M1 4l3 3 5-6" stroke="#080d16" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </span>
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={checked}
                      onChange={() => toggleSubject(subj)}
                    />
                    <span className="font-sans text-sm flex-1">{subj}</span>
                    <span className="font-mono text-[0.65rem] text-dim">
                      ({subjectCounts[subj]} available)
                    </span>
                  </label>
                )
              })}
            </div>
          )}
        </Section>

        {/* ── Difficulty filter ────────────────────────────────────── */}
        <Section label="Difficulty" hint="Optional">
          <div className="flex gap-2 flex-wrap">
            {DIFFICULTY_OPTIONS.map(opt => {
              const active = difficulty === opt.value
              return (
                <button
                  key={opt.value}
                  onClick={() => setDifficulty(opt.value)}
                  className={[
                    'font-mono text-xs tracking-wider uppercase px-4 py-1.5 border transition-all cursor-pointer',
                    active
                      ? 'border-gold bg-gold/10 text-gold'
                      : 'border-border bg-surface2 text-muted hover:border-border2 hover:bg-surface3',
                  ].join(' ')}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </Section>

        {/* ── Summary bar ──────────────────────────────────────────── */}
        <div className="bg-surface2 border border-border px-5 py-3.5 flex items-center gap-3 flex-wrap">
          <span className="font-mono text-[0.6rem] tracking-[0.15em] uppercase text-muted shrink-0">
            Summary
          </span>
          <span className="w-px h-4 bg-border shrink-0" />
          <p className="font-mono text-xs text-ink">
            <span className="text-gold font-semibold">{summaryCount}</span>
            {' '}question{summaryCount !== 1 ? 's' : ''}
            {' · '}
            <span className={mode ? 'text-ink' : 'text-dim'}>{summaryMode}</span>
            {' · '}
            <span className="text-ink">{summarySubj}</span>
            {summaryDiff && (
              <span className="text-ink">{summaryDiff}</span>
            )}
          </p>
        </div>

        {/* ── Start button ─────────────────────────────────────────── */}
        <div className="pt-2">
          {!mode && (
            <p className="font-mono text-xs text-muted mb-3 flex items-center gap-1.5">
              <span className="text-wrong">*</span> Select a mode to enable Start Test
            </p>
          )}
          <button
            onClick={handleStart}
            disabled={!mode || loadingQ || bankTotal === 0}
            className={[
              'btn btn-primary btn-lg w-full justify-center text-sm tracking-wide',
              (!mode || loadingQ || bankTotal === 0)
                ? 'opacity-40 cursor-not-allowed'
                : '',
            ].join(' ')}
          >
            {loadingQ ? 'Loading…' : 'Start Test →'}
          </button>
        </div>

      </div>
    </main>
  )
}

// ── Section wrapper ──────────────────────────────────────────────────────────
function Section({ label, hint, required, children }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline gap-2">
        <p className="section-title">{label}</p>
        {required && (
          <span className="font-mono text-[0.6rem] tracking-widest uppercase text-wrong">required</span>
        )}
        {hint && !required && (
          <span className="font-mono text-[0.6rem] text-dim">{hint}</span>
        )}
      </div>
      {children}
    </div>
  )
}

// ── Mode card ────────────────────────────────────────────────────────────────
function ModeCard({ active, onClick, title, icon, description }) {
  return (
    <button
      onClick={onClick}
      className={[
        'flex flex-col gap-3 p-5 text-left border transition-all cursor-pointer w-full',
        active
          ? 'border-gold bg-gold/8 ring-1 ring-gold/20'
          : 'border-border bg-surface2 hover:border-border2 hover:bg-surface3',
      ].join(' ')}
    >
      <div className="flex items-center justify-between">
        <span className={[
          'flex items-center justify-center w-9 h-9 border',
          active ? 'border-gold/40 bg-gold/10 text-gold' : 'border-border2 bg-surface3 text-muted',
        ].join(' ')}>
          {icon}
        </span>
        {/* Radio-style indicator */}
        <span className={[
          'w-4 h-4 border-2 rounded-full flex items-center justify-center shrink-0 transition-all',
          active ? 'border-gold' : 'border-border2',
        ].join(' ')}>
          {active && <span className="w-2 h-2 rounded-full bg-gold block" />}
        </span>
      </div>
      <div>
        <p className={[
          'font-display text-base font-bold tracking-tight mb-1',
          active ? 'text-bright' : 'text-ink',
        ].join(' ')}>
          {title}
        </p>
        <p className="font-sans text-xs text-muted leading-relaxed">{description}</p>
      </div>
    </button>
  )
}

// ── Icons ────────────────────────────────────────────────────────────────────
function ClockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function BookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  )
}
