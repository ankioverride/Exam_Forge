const KEY = 'examprep_bookmarks'

export function getBookmarks() {
  return JSON.parse(localStorage.getItem(KEY) || '[]')
}

export function isBookmarked(questionId) {
  return getBookmarks().some(b => b.id === questionId)
}

export function addBookmark(question, exam) {
  const existing = getBookmarks()
  if (existing.some(b => b.id === question.id)) return
  const updated = [
    {
      id: question.id,
      exam,
      subject: question.subject,
      text: question.text,
      options: question.options,
      correct: question.correct,
      explanation: question.explanation,
      savedAt: new Date().toISOString(),
    },
    ...existing,
  ]
  localStorage.setItem(KEY, JSON.stringify(updated))
}

export function removeBookmark(questionId) {
  const updated = getBookmarks().filter(b => b.id !== questionId)
  localStorage.setItem(KEY, JSON.stringify(updated))
}

export function toggleBookmark(question, exam) {
  if (isBookmarked(question.id)) removeBookmark(question.id)
  else addBookmark(question, exam)
}
