#!/usr/bin/env python3
"""
Gemini Master Pipeline
-----------------------
Three phases, all delegated to Gemini 2.5:

  Phase 1 — QC: Verify every question's correct answer, add/fix explanations.
             Sends 25 questions per API call. Updates src/data/*.json in place.

  Phase 2 — Generate: Fill weak subjects for UPSC, APSC, and CAT.

  Phase 3 — Merge: Run pipeline.py to rebuild all three exam files.

Usage:
    python gemini_master.py                    # all three phases
    python gemini_master.py --phase qc         # only QC
    python gemini_master.py --phase generate   # only generation
    python gemini_master.py --phase qc --exam upsc
    python gemini_master.py --phase generate --exam cat
"""

import re
import json
import time
import copy
import logging
import argparse
import subprocess
from pathlib import Path

from google import genai
from google.genai import types

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gemini_master.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = 'REDACTED_API_KEY'
MODEL          = 'gemini-2.5-flash'   # fast + cheap for bulk; Pro for generation
GEN_MODEL      = 'gemini-2.5-pro'
FALLBACK       = 'gemini-2.5-flash'

SCRIPT_DIR  = Path(__file__).parent
DATA_DIR    = SCRIPT_DIR.parent.parent / 'src' / 'data'
RAW_DIR     = SCRIPT_DIR / 'raw'

QC_BATCH    = 25   # questions per API call for QC
GEN_BATCH   = 50   # questions per API call for generation

# ── Target question counts per subject ─────────────────────────────────────
TARGETS = {
    'upsc': {
        'History':       500,
        'Geography':     300,
        'Polity':        250,
        'Economy':       200,
        'Environment':   150,
        'Science & Tech': 300,
    },
    'apsc': {
        'Assam History':   200,
        'Assam Geography': 200,
        'Art & Culture':   200,
        'Polity':          200,
        'Economy':         150,
        'Environment':     150,
        'History':         400,
        'Science':         150,
    },
    'cat': {
        'Quantitative Aptitude': 600,
        'Verbal Ability':        600,
        'Data Interpretation':   300,
        'Logical Reasoning':     300,
    },
}

# ── Subject generation prompts ──────────────────────────────────────────────
GEN_CONTEXT = {
    # UPSC
    'History': {
        'exam': 'UPSC Civil Services',
        'scope': 'Indian and World History: ancient civilisations, Vedic period, Maurya, Gupta, Delhi Sultanate, Mughal Empire, British colonialism, Indian National Movement, Partition, post-independence events. Key figures, battles, treaties, reforms.'
    },
    'Geography': {
        'exam': 'UPSC Civil Services',
        'scope': 'Indian and World Physical Geography: landforms, rivers, climate, soils, natural vegetation, oceans, tectonic plates, rocks. Economic Geography: resources, industries, agriculture, urbanisation. Important geographic phenomena, recent disasters, maps.'
    },
    'Polity': {
        'exam': 'UPSC Civil Services',
        'scope': 'Indian Constitution, Fundamental Rights and Duties, DPSP, Preamble, Parliament, President, Prime Minister, Supreme Court, High Courts, Elections, Local Self-Government, Constitutional Amendments, Emergency Provisions, Important Articles.'
    },
    'Economy': {
        'exam': 'UPSC Civil Services',
        'scope': 'Indian Economy: Five-Year Plans, GDP, inflation, monetary policy, fiscal policy, RBI, SEBI, banking, taxation (GST, direct taxes), agriculture economy, industrial policy, trade, BOP, poverty, unemployment, economic surveys, budget highlights.'
    },
    'Environment': {
        'exam': 'UPSC Civil Services',
        'scope': 'Ecology, biodiversity, climate change, National Parks and Wildlife Sanctuaries, environmental laws (Wildlife Protection Act, Forest Conservation Act, Environment Protection Act), international agreements (Paris Agreement, Kyoto Protocol, Convention on Biodiversity), pollution, sustainable development.'
    },
    'Science & Tech': {
        'exam': 'UPSC Civil Services',
        'scope': 'Basic Science: physics, chemistry, biology concepts. Space: ISRO missions, NASA, satellites. Defence technology: missiles, nuclear. IT: AI, blockchain, cybersecurity. Biotechnology: GMO, vaccines, DNA. Recent inventions, Nobel prizes in science, government S&T schemes.'
    },
    # APSC
    'Assam History': {
        'exam': 'APSC CCE',
        'scope': 'Ahom Kingdom (1228–1826), Sukaphaa, Lachit Borphukan, Battle of Saraighat 1671, Treaty of Yandabo 1826, Koch Kingdom (Naranarayan, Chilarai), Kachari Kingdom, Baro-Bhuiyans, Moamoria Rebellion, Maniram Dewan, Phulaguri Dhawa 1861, Assam Agitation (1979–85), Assam Accord 1985, NRC history.'
    },
    'Assam Geography': {
        'exam': 'APSC CCE',
        'scope': 'Brahmaputra river system (tributaries: Subansiri, Jiabharali, Lohit, Kopili, Barak), Majuli island, 35 districts of Assam, Kaziranga, Manas, Nameri, Orang, Dibru-Saikhowa national parks, Deepor Beel (Ramsar site), Karbi Anglong hills, Barail Range, Assam borders.'
    },
    'Art & Culture': {
        'exam': 'APSC CCE',
        'scope': 'Bihu (Rongali/Bohag, Kongali/Kati, Bhogali/Magh), Sattriya dance (classical, UNESCO), Borgeet, Sankardeva (1449–1568), Madhabdeva, Ankiya Naat, Ojapali, Muga silk (Antheraea assamensis), Sualkuchi town, Nam Ghar (prayer hall), Satra (monasteries), Dhol/Pepa/Gogona instruments, Gamocha, Jaapi, Xah phakori, Bihu dance.'
    },
    'Science': {
        'exam': 'APSC CCE',
        'scope': 'Basic science: physics (motion, electricity, optics), chemistry (periodic table, acids/bases, carbon compounds), biology (cell, genetics, evolution, human body systems). ISRO missions, Indian science achievements. Environmental science relevant to Assam (floods, erosion, wildlife).'
    },
    # CAT
    'Quantitative Aptitude': {
        'exam': 'CAT (Common Admission Test)',
        'scope': 'Number systems, percentages, profit and loss, simple/compound interest, ratio and proportion, time-speed-distance, time and work, averages, mixtures, algebra (equations, inequalities), geometry (triangles, circles, quadrilaterals), mensuration, permutations and combinations, probability, set theory. Medium to hard difficulty.'
    },
    'Verbal Ability': {
        'exam': 'CAT (Common Admission Test)',
        'scope': 'Reading comprehension passages, para-jumbles (arrange sentences), para-summary, odd sentence out, sentence correction, fill in the blanks (grammar/vocabulary), analogies, critical reasoning. Medium to hard difficulty. Focus on inference, main idea, logical reasoning through language.'
    },
    'Data Interpretation': {
        'exam': 'CAT (Common Admission Test)',
        'scope': 'Bar charts, line graphs, pie charts, tables, combination charts — each with 3-4 questions about reading data, calculating percentages, finding ratios, making comparisons, computing averages. Medium to hard difficulty. Questions must reference specific data points from a described chart/table.'
    },
    'Logical Reasoning': {
        'exam': 'CAT (Common Admission Test)',
        'scope': 'Seating arrangements (linear/circular), blood relations, directions, coding-decoding, syllogisms, analogies, series completion, input-output, puzzles. Deductive reasoning, clue-based problems. Medium to hard difficulty for CAT level.'
    },
}


# ───────────────────────────── API Helper ────────────────────────────────────

def call(client, prompt: str, model: str = MODEL, temperature: float = 0.1) -> str:
    """Call Gemini with automatic fallback on 503."""
    models_to_try = [model]
    if model != FALLBACK:
        models_to_try.append(FALLBACK)

    for m in models_to_try:
        for attempt in range(3):
            try:
                r = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=16384,
                    ),
                )
                return r.text or ''
            except Exception as e:
                err = str(e)
                if '503' in err or 'UNAVAILABLE' in err:
                    wait = (attempt + 1) * 10
                    logger.warning(f"  {m} overloaded (attempt {attempt+1}), waiting {wait}s ...")
                    time.sleep(wait)
                elif '429' in err or 'quota' in err.lower():
                    logger.warning(f"  Rate limit, sleeping 60s ...")
                    time.sleep(60)
                else:
                    logger.error(f"  {m} error: {err[:120]}")
                    break
        else:
            continue  # inner loop exhausted, try next model
        break
    return ''


def parse_json_array(raw: str) -> list:
    """Extract first valid JSON array from Gemini output."""
    # Strip markdown fences
    raw = re.sub(r'```json?\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = raw.strip()
    # Try full parse
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass
    # Try to find array
    m = re.search(r'\[.+\]', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return []


def parse_jsonl(raw: str) -> list:
    """Parse newline-delimited JSON objects."""
    results = []
    for line in raw.split('\n'):
        line = line.strip().strip('`')
        if line.startswith('{'):
            try:
                results.append(json.loads(line))
            except Exception:
                try:
                    results.append(json.loads(re.sub(r',\s*}', '}', line)))
                except Exception:
                    pass
    return results


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — QC
# ══════════════════════════════════════════════════════════════════════════════

QC_PROMPT = """\
You are a fact-checker for competitive exam questions.

I will give you a JSON array of {n} questions. For EACH question:
1. Verify whether the "correct" index (0=A, 1=B, 2=C, 3=D) is actually correct.
2. If the answer is WRONG, set the right index in "correct" and note the fix.
3. If "explanation" is empty or weak, write a clear 1–2 sentence explanation.
4. Keep "id", "subject", "difficulty", "text", "options" UNCHANGED.

Return ONLY a JSON array (no markdown, no text) with the same {n} objects,
each having: id, correct (verified/fixed), explanation (filled/improved).

Questions:
{questions_json}
"""


def qc_exam(client, exam: str):
    path = DATA_DIR / f'{exam}.json'
    questions = json.load(open(path, encoding='utf-8'))
    logger.info(f"\n{'='*60}\nQC: {exam.upper()} — {len(questions)} questions\n{'='*60}")

    updated = {q['id']: q for q in questions}
    changes = 0
    needs_qc = [q for q in questions if not q.get('explanation', '').strip() or True]  # QC all

    for i in range(0, len(needs_qc), QC_BATCH):
        batch = needs_qc[i: i + QC_BATCH]
        compact = [{'id': q['id'], 'text': q['text'], 'options': q['options'],
                    'correct': q['correct'], 'explanation': q.get('explanation', '')}
                   for q in batch]

        prompt = QC_PROMPT.format(n=len(compact), questions_json=json.dumps(compact, ensure_ascii=False))
        raw = call(client, prompt, model=MODEL)
        if not raw:
            logger.warning(f"  Batch {i//QC_BATCH+1}: empty response, skipping")
            continue

        results = parse_json_array(raw)
        if not results:
            results = parse_jsonl(raw)

        for r in results:
            qid = r.get('id')
            if not qid or qid not in updated:
                continue
            old = updated[qid]
            changed = False
            if isinstance(r.get('correct'), int) and r['correct'] in (0,1,2,3):
                if old['correct'] != r['correct']:
                    logger.info(f"  FIXED answer: [{qid}] {old['text'][:50]!r} → {r['correct']}")
                    updated[qid] = dict(old, correct=r['correct'])
                    changed = True
            exp = r.get('explanation', '').strip()
            if exp and exp != old.get('explanation', '').strip():
                updated[qid] = dict(updated[qid], explanation=exp)
                changed = True
            if changed:
                changes += 1

        pct = (i + len(batch)) / len(needs_qc) * 100
        logger.info(f"  Progress: {i+len(batch)}/{len(needs_qc)} ({pct:.0f}%) | changes so far: {changes}")
        time.sleep(1)

    # Save
    final = [updated[q['id']] for q in questions]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    logger.info(f"  Saved {exam}.json — {changes} questions improved/fixed")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — GENERATE
# ══════════════════════════════════════════════════════════════════════════════

GEN_PROMPT = """\
You are creating MCQ questions for {exam}.

SUBJECT: {subject}
SCOPE: {scope}

ALREADY EXISTS (do NOT repeat):
{existing_sample}

Generate exactly {n} unique, accurate MCQs. Each on its own line as JSON:
{{"q":"question","a":"opt A","b":"opt B","c":"opt C","d":"opt D","ans":"A|B|C|D","exp":"1-2 sentence explanation"}}

Rules:
- Only one correct answer; others must be plausible but clearly wrong
- All facts must be verifiable and accurate
- Mix question types: definition, cause/effect, identification, comparison
- No duplicate or near-duplicate questions
- Output ONLY the JSON lines, nothing else
"""

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
VALID_SUBJECTS = {
    'upsc': {'History', 'Geography', 'Polity', 'Economy', 'Environment', 'Science & Tech'},
    'apsc': {'Assam History', 'Assam Geography', 'Art & Culture', 'History', 'Geography',
             'Polity', 'Economy', 'Environment', 'Science'},
    'cat':  {'Quantitative Aptitude', 'Verbal Ability', 'Data Interpretation', 'Logical Reasoning'},
}


def generate_subject(client, exam: str, subject: str, n: int,
                     existing_texts: list[str]) -> list[dict]:
    ctx = GEN_CONTEXT.get(subject, {})
    sample = '\n'.join(f'- {t[:80]}' for t in existing_texts[-30:])
    prompt = GEN_PROMPT.format(
        exam=ctx.get('exam', exam.upper()),
        subject=subject,
        scope=ctx.get('scope', f'{subject} topics relevant to {exam.upper()}'),
        existing_sample=sample or '(none yet)',
        n=n,
    )

    raw = call(client, prompt, model=GEN_MODEL, temperature=0.7)
    if not raw:
        return []

    questions = []
    seen = set()
    for line in raw.split('\n'):
        line = line.strip().strip('`')
        if not line.startswith('{'):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            try:
                obj = json.loads(re.sub(r',\s*}', '}', line))
            except Exception:
                continue

        q_text = obj.get('q', '').strip()
        if len(q_text) < 10:
            continue
        opts = [obj.get(k, '').strip() for k in ['a', 'b', 'c', 'd']]
        if any(len(o) < 1 for o in opts):
            continue
        ans = obj.get('ans', '').strip().upper()
        correct_idx = ANSWER_MAP.get(ans)
        if correct_idx is None:
            continue
        norm = re.sub(r'\s+', ' ', q_text.lower())
        if norm in seen:
            continue
        seen.add(norm)
        questions.append({
            'id':          f"gen-{exam}-{subject.replace(' ','_')}-{len(questions)}",
            'subject':     subject,
            'difficulty':  'medium',
            'text':        q_text,
            'options':     opts,
            'correct':     correct_idx,
            'explanation': obj.get('exp', '').strip(),
            'source':      'gemini-generated',
        })
    return questions


def generate_exam(client, exam: str):
    path = DATA_DIR / f'{exam}.json'
    questions = json.load(open(path, encoding='utf-8'))
    from collections import Counter
    counts = Counter(q['subject'] for q in questions)
    targets = TARGETS.get(exam, {})

    logger.info(f"\n{'='*60}\nGENERATE: {exam.upper()}\n{'='*60}")

    all_new = []
    for subject, target in targets.items():
        current = counts.get(subject, 0)
        need = max(0, target - current)
        if need <= 0:
            logger.info(f"  {subject}: {current}/{target} — already at target, skipping")
            continue
        logger.info(f"  {subject}: {current}/{target} — generating {need} questions")

        existing_texts = [q['text'] for q in questions if q['subject'] == subject]

        # Generate in batches
        subject_qs = []
        for batch_start in range(0, need, GEN_BATCH):
            this_batch = min(GEN_BATCH, need - len(subject_qs))
            if this_batch <= 0:
                break
            batch_qs = generate_subject(
                client, exam, subject, this_batch,
                existing_texts + [q['text'] for q in subject_qs]
            )
            subject_qs.extend(batch_qs)
            logger.info(f"    Batch done: {len(batch_qs)} | Total: {len(subject_qs)}")
            time.sleep(3)

        all_new.extend(subject_qs)
        logger.info(f"  {subject}: +{len(subject_qs)} generated")

    if all_new:
        # Assign proper IDs
        prefix = {'upsc': 'u', 'apsc': 'a', 'cat': 'c'}[exam]
        start = len(questions) + 1
        for i, q in enumerate(all_new):
            q['id'] = f"{prefix}{start + i}"

        merged = questions + all_new
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        logger.info(f"  Saved {exam}.json: {len(questions)} + {len(all_new)} = {len(merged)} total")
    else:
        logger.info(f"  No new questions needed for {exam}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['qc', 'generate', 'all'], default='all')
    parser.add_argument('--exam',  choices=['upsc', 'apsc', 'cat', 'all'], default='all')
    args = parser.parse_args()

    client = genai.Client(api_key=GEMINI_API_KEY)
    exams  = ['upsc', 'apsc', 'cat'] if args.exam == 'all' else [args.exam]

    if args.phase in ('qc', 'all'):
        logger.info("\n▶ PHASE 1: QC — Verify answers + fill explanations")
        for exam in exams:
            qc_exam(client, exam)

    if args.phase in ('generate', 'all'):
        logger.info("\n▶ PHASE 2: GENERATE — Fill weak subjects")
        for exam in exams:
            generate_exam(client, exam)

    logger.info("\n✓ All done.")


if __name__ == '__main__':
    main()
