import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const EXAMS = [
  {
    key:         'upsc',
    code:        'UPSC',
    title:       'Civil Services Prelims',
    org:         'Union Public Service Commission',
    desc:        'General Studies Paper I — History, Geography, Polity, Economy, Science & Environment.',
    marks:       '+2 / −0.66',
    time:        '20 min',
    qs:          '10 Questions',
    accentClass: 'border-t-2 border-t-gold',
    tagCls:      'tag tag-gold',
  },
  {
    key:         'apsc',
    code:        'APSC',
    title:       'Assam Civil Services Prelims',
    org:         'Assam Public Service Commission',
    desc:        'General Studies with focus on Assam — History, Geography, Culture, Polity & Economy.',
    marks:       '+2 / −0.5',
    time:        '20 min',
    qs:          '10 Questions',
    accentClass: 'border-t-2 border-t-correct',
    tagCls:      'tag tag-green',
  },
  {
    key:         'cat',
    code:        'CAT',
    title:       'Common Admission Test',
    org:         'Indian Institutes of Management',
    desc:        'Quantitative Aptitude, Verbal Ability, and Data Interpretation & Logical Reasoning.',
    marks:       '+3 / −1',
    time:        '15 min',
    qs:          '10 Questions',
    accentClass: 'border-t-2 border-t-wrong',
    tagCls:      'tag tag-red',
  },
]

export default function Tests() {
  const navigate = useNavigate()
  const { user, signInWithGoogle } = useAuth()
  const [pendingExam, setPendingExam] = useState(null)
  const [pendingMode, setPendingMode] = useState('timed')

  // Once signed in, auto-navigate to the pending exam+mode
  useEffect(() => {
    if (user && pendingExam) {
      const url = pendingMode === 'custom'
        ? `/configure/${pendingExam}`
        : `/test/${pendingExam}?mode=${pendingMode}`
      navigate(url)
      setPendingExam(null)
    }
  }, [user, pendingExam, pendingMode, navigate])

  function handleStartTest(examKey, mode = 'timed') {
    if (user) {
      const url = mode === 'custom'
        ? `/configure/${examKey}`
        : `/test/${examKey}?mode=${mode}`
      navigate(url)
    } else {
      setPendingMode(mode)
      setPendingExam(examKey)
    }
  }

  return (
    <>
      <main className="max-w-5xl mx-auto px-6 py-14">

        {/* ── Page header ────────────────────────────────── */}
        <div className="mb-12">
          <div className="flex items-center gap-2 font-mono text-[0.7rem] tracking-[0.18em] uppercase text-gold mb-5">
            <span className="w-8 h-px bg-gold inline-block" />
            Mock Test Platform · UPSC · APSC · CAT
          </div>
          <h1 className="font-display text-4xl lg:text-5xl font-bold text-bright tracking-tight leading-[1.1] mb-4">
            Choose your exam.
          </h1>
          <p className="text-muted text-base max-w-xl leading-relaxed">
            Timed mock tests with real negative marking, instant solution review, and progress tracking.
          </p>
        </div>

        {/* ── Exam Cards ─────────────────────────────────── */}
        <div className="mb-4">
          <p className="section-title">Available tests</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border border border-border">
          {EXAMS.map(exam => (
            <div
              key={exam.key}
              className={`bg-surface hover:bg-surface2 transition-colors flex flex-col ${exam.accentClass}`}
            >
              <div className="p-6 flex flex-col gap-3 flex-1">
                <span className={exam.tagCls}>{exam.code}</span>
                <h3 className="font-display text-lg font-bold text-bright tracking-tight leading-snug">
                  {exam.title}
                </h3>
                <p className="font-mono text-[0.65rem] tracking-wider uppercase text-muted">{exam.org}</p>
                <p className="text-sm text-muted leading-relaxed flex-1">{exam.desc}</p>

                {/* Meta chips */}
                <div className="flex gap-2 flex-wrap pt-1">
                  <Chip label="Marks" val={exam.marks} />
                  <Chip label="Time"  val={exam.time} />
                  <Chip label="Qs"    val={exam.qs} />
                </div>
              </div>

              {/* Card footer */}
              <div className="px-6 py-4 border-t border-border bg-surface2/40 flex flex-col gap-2">
                <div className="flex gap-2">
                  <button
                    onClick={() => handleStartTest(exam.key, 'timed')}
                    className="btn btn-primary btn-sm flex-1 justify-center"
                  >
                    ⏱ Timed
                  </button>
                  <button
                    onClick={() => handleStartTest(exam.key, 'practice')}
                    className="btn btn-outline btn-sm flex-1 justify-center"
                  >
                    Practice
                  </button>
                </div>
                <button
                  onClick={() => handleStartTest(exam.key, 'custom')}
                  className="btn btn-ghost btn-sm w-full justify-center text-xs text-muted"
                >
                  ⚙ Custom Test →
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* ── Sign-in gate modal ──────────────────────────── */}
      {pendingExam && !user && (
        <div className="fixed inset-0 bg-bg/90 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-border2 p-8 max-w-sm w-full">
            {/* Header */}
            <div className="mb-6">
              <p className="font-mono text-[0.65rem] tracking-widest uppercase text-gold mb-2">
                Sign in required
              </p>
              <h2 className="font-display text-2xl font-bold text-bright tracking-tight mb-2">
                Ready to attempt?
              </h2>
              <p className="text-sm text-muted leading-relaxed">
                Sign in with Google to start the{' '}
                <span className="text-ink font-semibold">
                  {EXAMS.find(e => e.key === pendingExam)?.code}
                </span>{' '}
                test. Your score and progress will be saved.
              </p>
            </div>

            {/* What you get */}
            <div className="border border-border bg-surface2 p-4 mb-6 flex flex-col gap-2">
              {['Test history saved to cloud', 'Weak area tracking', 'Progress across devices'].map(item => (
                <div key={item} className="flex items-center gap-2">
                  <span className="text-correct text-xs">✓</span>
                  <span className="text-xs text-muted">{item}</span>
                </div>
              ))}
            </div>

            <div className="flex flex-col gap-3">
              <button
                onClick={signInWithGoogle}
                className="btn btn-primary w-full justify-center gap-2 py-3 text-sm"
              >
                <GoogleIcon />
                Continue with Google
              </button>
              <button
                onClick={() => setPendingExam(null)}
                className="btn btn-ghost w-full justify-center text-xs text-muted"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function Chip({ label, val }) {
  return (
    <div className="bg-surface3 border border-border px-2 py-0.5 flex items-center gap-1.5">
      <span className="font-mono text-[0.58rem] tracking-widest uppercase text-dim">{label}</span>
      <span className="font-mono text-[0.7rem] font-semibold text-ink">{val}</span>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  )
}
