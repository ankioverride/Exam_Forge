// ── Exam config ─────────────────────────────────────────────────────────────
export const EXAM_CONFIG = {
  upsc: {
    name:          'UPSC Prelims',
    fullName:      'Union Public Service Commission — General Studies Paper I',
    timeMinutes:   20,
    correctMarks:  2,
    negativeMarks: 0.666,
    desc:          'General Studies covering History, Geography, Polity, Economy, Science & Environment.',
    sessionQ:      10,
  },
  apsc: {
    name:          'APSC Prelims',
    fullName:      'Assam Public Service Commission — General Studies',
    timeMinutes:   20,
    correctMarks:  2,
    negativeMarks: 0.5,
    desc:          'General Studies with focus on Assam — History, Geography, Culture, Polity, Economy.',
    sessionQ:      10,
  },
  cat: {
    name:          'CAT',
    fullName:      'Common Admission Test — Mixed Sections',
    timeMinutes:   15,
    correctMarks:  3,
    negativeMarks: 1,
    desc:          'Quantitative Aptitude, Verbal Ability & Reading Comprehension, Data Interpretation & Logical Reasoning.',
    sessionQ:      10,
  },
}

// ── Async question loader ────────────────────────────────────────────────────
export async function loadQuestions(exam, opts = {}) {
  const mod = await import(`./${exam}.json`)
  let qs = [...mod.default]

  // Filter by subjects if provided
  if (opts.subjects?.length) qs = qs.filter(q => opts.subjects.includes(q.subject))
  if (opts.difficulty) qs = qs.filter(q => q.difficulty === opts.difficulty)

  // Shuffle
  for (let i = qs.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [qs[i], qs[j]] = [qs[j], qs[i]]
  }

  // Slice to session size
  const count = opts.count || EXAM_CONFIG[exam]?.sessionQ || 10
  return qs.slice(0, count)
}
