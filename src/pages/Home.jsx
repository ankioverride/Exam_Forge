import { Link } from 'react-router-dom'
import QuestionOfTheDay from '../components/QuestionOfTheDay'

// ── Data ──────────────────────────────────────────────────────────────────────

const STEPS = [
  {
    num: '01',
    title: 'Pick Your Exam',
    body: "Choose from UPSC Civil Services Prelims, APSC General Studies, or CAT. Each test mirrors the real exam's marking scheme.",
  },
  {
    num: '02',
    title: 'Take a Timed Test',
    body: 'A countdown timer runs throughout. Questions are locked on submit. Negative marking is applied exactly as in the actual exam.',
  },
  {
    num: '03',
    title: 'Review Every Solution',
    body: 'After submission, read detailed explanations for each question. Filter by correct, wrong, or skipped to focus your revision.',
  },
]

const FEATURES = [
  {
    tag: 'Accuracy',
    title: 'Real Negative Marking',
    body: 'UPSC deducts ⅓, APSC deducts ¼, CAT deducts ⅓ — exactly as the official scheme. No watered-down simulation.',
  },
  {
    tag: 'Discipline',
    title: 'Countdown Timer',
    body: 'Each test runs under a strict timer. Auto-submits on expiry. Build the time-management muscle before exam day.',
  },
  {
    tag: 'Insight',
    title: 'Solution Review',
    body: 'Every question comes with a written explanation. Revisit the full attempt after submission — correct, wrong, and skipped.',
  },
  {
    tag: 'Memory',
    title: 'Progress Tracking',
    body: 'Your test history and subject-wise scores are saved. Sign in with Google to sync across devices.',
  },
]

const STATS = [
  { val: '3',    label: 'Exams' },
  { val: '6,707', label: 'Questions' },
  { val: 'Real', label: 'Negative Marking' },
  { val: 'Free', label: 'Always' },
]

const EXAMS = [
  { code: 'UPSC', label: 'Civil Services Prelims', tagCls: 'tag tag-gold' },
  { code: 'APSC', label: 'Assam Civil Services',   tagCls: 'tag tag-green' },
  { code: 'CAT',  label: 'Common Admission Test',  tagCls: 'tag tag-red' },
]

// ── Component ─────────────────────────────────────────────────────────────────

export default function Home() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-16">

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <section className="mb-20">

        {/* Eyebrow */}
        <div className="flex items-center gap-3 mb-6">
          <span className="w-8 h-px bg-gold" />
          <span className="font-mono text-[0.68rem] tracking-[0.2em] uppercase text-gold">
            Mock Test Platform · Indian Competitive Exams
          </span>
        </div>

        {/* Headline */}
        <h1 className="font-display text-5xl lg:text-[3.75rem] font-bold text-bright tracking-tight leading-[1.08] mb-6">
          Prepare seriously.<br />
          <span className="text-gold italic">Score honestly.</span>
        </h1>

        {/* Subtext */}
        <p className="text-muted text-base max-w-2xl leading-relaxed mb-10">
          Timed mock tests with real negative marking, question-by-question solution review,
          and performance tracking. Built for UPSC, APSC, and CAT aspirants who want exam-day
          conditions, not comfortable practice.
        </p>

        {/* CTA row */}
        <div className="flex items-center gap-4 flex-wrap mb-12">
          <Link to="/tests" className="btn btn-primary btn-lg">
            Browse Tests →
          </Link>
          <Link to="/dashboard" className="btn btn-outline btn-lg">
            My Progress
          </Link>
        </div>

        {/* Exam badges */}
        <div className="flex items-center gap-3 flex-wrap mb-12">
          {EXAMS.map(e => (
            <span key={e.code} className={e.tagCls}>{e.code}</span>
          ))}
          <span className="font-mono text-[0.65rem] tracking-widest uppercase text-muted ml-1">
            — {EXAMS.map(e => e.label).join(' · ')}
          </span>
        </div>

        {/* Stats bar */}
        <div className="border-t border-border pt-8 grid grid-cols-2 md:grid-cols-4 gap-px bg-border border-x border-b border-border">
          {STATS.map(s => (
            <div key={s.label} className="bg-bg px-6 py-5">
              <p className="font-mono text-2xl font-semibold text-bright tracking-tight mb-0.5">
                {s.val}
              </p>
              <p className="font-mono text-[0.62rem] tracking-[0.18em] uppercase text-muted">
                {s.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Question of the Day ───────────────────────────────────────────── */}
      <section className="mb-20">
        <p className="section-title">Question of the Day</p>
        <QuestionOfTheDay />
      </section>

      {/* ── How it works ──────────────────────────────────────────────────── */}
      <section className="mb-20">
        <p className="section-title">How it works</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-border border border-border">
          {STEPS.map(step => (
            <div key={step.num} className="bg-surface p-7 flex flex-col gap-4">
              {/* Step number */}
              <span className="font-mono text-[2.5rem] font-bold text-border2 leading-none select-none">
                {step.num}
              </span>

              {/* Divider */}
              <div className="w-8 h-px bg-gold" />

              <h3 className="font-display text-lg font-bold text-bright tracking-tight leading-snug">
                {step.title}
              </h3>
              <p className="text-sm text-muted leading-relaxed flex-1">
                {step.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ──────────────────────────────────────────────────────── */}
      <section className="mb-20">
        <p className="section-title">Platform features</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-border border border-border">
          {FEATURES.map(f => (
            <div key={f.title} className="bg-surface p-7 flex flex-col gap-3">
              <span className="tag tag-grey self-start">{f.tag}</span>
              <h3 className="font-display text-base font-bold text-bright tracking-tight">
                {f.title}
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── About ─────────────────────────────────────────────────────────── */}
      <section className="mb-20">
        <p className="section-title">About ExamForge</p>

        <div className="border border-border bg-surface p-8 max-w-3xl">
          <p className="text-sm text-muted leading-[1.85]">
            ExamForge was built out of frustration with practice platforms that soften the exam
            experience — no real timers, optional negative marking, vague solutions. This platform
            exists to give UPSC, APSC, and CAT aspirants a faithful replica of actual test
            conditions: strict countdowns, accurate penalty deductions, and clear post-test
            explanations for every question. It is free to use, no ads, no paywalls. Sign in to
            unlock cross-device progress sync; or use it without an account.
          </p>
        </div>
      </section>

      {/* ── Bottom CTA ────────────────────────────────────────────────────── */}
      <section>
        <div className="border border-border2 bg-surface p-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <p className="font-mono text-[0.68rem] tracking-[0.2em] uppercase text-gold mb-2">
              Start now — it's free
            </p>
            <h2 className="font-display text-2xl font-bold text-bright tracking-tight leading-snug">
              Ready to test yourself?
            </h2>
          </div>
          <Link to="/tests" className="btn btn-primary btn-lg shrink-0">
            View All Tests →
          </Link>
        </div>
      </section>

    </main>
  )
}
