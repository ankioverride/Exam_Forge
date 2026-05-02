import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="bg-surface border-t border-border">
      {/* Main row */}
      <div className="flex items-center justify-between px-8 py-5">
        {/* Left — logo + tagline */}
        <div className="flex flex-col gap-1 shrink-0">
          <span className="font-display text-lg font-bold text-bright tracking-tight">
            Exam<span className="text-gold">Forge</span>
          </span>
          <span className="font-mono text-xs text-muted">Crack the exam. No shortcuts.</span>
        </div>

        {/* Center — nav links */}
        <nav className="flex items-center gap-1">
          {[
            { to: '/', label: 'Home' },
            { to: '/tests', label: 'Tests' },
            { to: '/dashboard', label: 'Dashboard' },
          ].map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className="font-mono text-xs text-muted hover:text-ink transition-colors px-3 py-1 border border-transparent hover:border-border no-underline"
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Right — audience */}
        <span className="font-mono text-xs text-muted shrink-0">
          Built for UPSC · APSC · CAT aspirants
        </span>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-border px-8 py-2.5">
        <p className="font-mono text-[0.65rem] text-muted text-center tracking-wide">
          © 2025 ExamForge · All questions are for practice only
        </p>
      </div>
    </footer>
  )
}
