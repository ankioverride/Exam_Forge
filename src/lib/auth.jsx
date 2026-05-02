import { createContext, useContext, useEffect, useState } from 'react'
import { GoogleAuthProvider, signInWithPopup, signOut as fbSignOut, onAuthStateChanged } from 'firebase/auth'
import { collection, addDoc, query, where, orderBy, getDocs, Timestamp } from 'firebase/firestore'
import { auth, db } from './firebase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // undefined = loading, null = signed out, object = signed in
  const [user, setUser] = useState(undefined)

  useEffect(() => onAuthStateChanged(auth, setUser), [])

  const signInWithGoogle = async () => {
    try {
      await signInWithPopup(auth, new GoogleAuthProvider())
    } catch (e) {
      console.warn('Sign-in failed:', e.message)
    }
  }

  const signOut = () => fbSignOut(auth)

  return (
    <AuthContext.Provider value={{ user, signInWithGoogle, signOut }}>
      {user !== undefined ? children : (
        <div className="min-h-screen bg-bg flex items-center justify-center">
          <span className="font-mono text-xs text-muted tracking-widest uppercase">Loading…</span>
        </div>
      )}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

// ── Firestore helpers ───────────────────────────────────────────
export async function saveAttempt(userId, attempt) {
  try {
    await addDoc(collection(db, 'attempts'), {
      userId,
      exam:      attempt.exam,
      score:     attempt.score,
      maxScore:  attempt.maxScore,
      correct:   attempt.correct,
      wrong:     attempt.wrong,
      skipped:   attempt.skipped,
      timeTaken:        attempt.timeTaken,
      mode:             attempt.mode ?? 'timed',
      subjectBreakdown: attempt.subjectBreakdown ?? [],
      date:             Timestamp.fromDate(new Date(attempt.date)),
    })
  } catch (e) {
    console.warn('Firestore save failed (offline?):', e.message)
  }
}

export async function fetchAttempts(userId) {
  try {
    const q = query(
      collection(db, 'attempts'),
      where('userId', '==', userId),
      orderBy('date', 'desc')
    )
    const snap = await getDocs(q)
    return snap.docs.map(d => ({ id: d.id, ...d.data(), date: d.data().date?.toDate()?.toISOString() }))
  } catch {
    return []
  }
}
