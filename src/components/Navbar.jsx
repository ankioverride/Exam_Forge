import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function Navbar() {
  const { user, signInWithGoogle, signOut } = useAuth()

  return (
    <nav className="bg-surface border-b border-border h-14 flex items-center justify-between px-8 sticky top-0 z-50">
      {/* Logo */}
      <Link to="/" className="font-display text-xl font-bold text-bright tracking-tight no-underline shrink-0">
        Exam<span className="text-gold">Forge</span>
      </Link>

      {/* Center nav links */}
      <div className="flex items-center gap-1">
        {[
          { to: '/', label: 'Home' },
          { to: '/tests', label: 'Tests' },
          { to: '/dashboard', label: 'Dashboard' },
          { to: '/bookmarks', label: 'Bookmarks' },
        ].map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `font-mono text-xs tracking-widest uppercase px-4 py-1.5 transition-colors no-underline border ${
                isActive
                  ? 'text-gold border-gold/30 bg-gold/8'
                  : 'text-muted border-transparent hover:text-ink hover:border-border2'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </div>

      {/* Right — auth */}
      <div className="flex items-center gap-3 shrink-0">
        {user ? (
          <>
            <div className="flex items-center gap-2.5 border-r border-border pr-3">
              {user.photoURL && (
                <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full border border-border2" />
              )}
              <div className="flex flex-col">
                <span className="font-mono text-xs text-bright leading-tight">{user.displayName?.split(' ')[0]}</span>
                <span className="font-mono text-[0.6rem] text-muted leading-tight truncate max-w-[120px]">{user.email}</span>
              </div>
            </div>
            <button
              onClick={signOut}
              className="font-mono text-xs text-muted hover:text-wrong border border-border hover:border-wrong/40 px-3 py-1.5 transition-colors bg-transparent cursor-pointer"
            >
              Sign out
            </button>
          </>
        ) : (
          <button
            onClick={signInWithGoogle}
            className="flex items-center gap-2 bg-surface2 border border-border2 text-ink text-sm font-semibold px-4 py-2 hover:border-gold hover:text-bright transition-colors cursor-pointer font-sans"
          >
            <GoogleIcon />
            Sign in
          </button>
        )}
      </div>
    </nav>
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
