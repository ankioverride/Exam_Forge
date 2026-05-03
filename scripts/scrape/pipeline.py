#!/usr/bin/env python3
"""
Pipeline — Raw → Cleaned JSON
-------------------------------
Reads all raw scraped files from scripts/scrape/raw/, deduplicates,
validates, and merges into src/data/{exam}.json alongside existing questions.

Usage:
    python pipeline.py                   # merge all exams
    python pipeline.py --exam upsc       # only UPSC
    python pipeline.py --exam cat
    python pipeline.py --exam apsc
    python pipeline.py --stats           # just print stats, don't write
"""

import json
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR  = Path(__file__).parent
RAW_DIR     = SCRIPT_DIR / "raw"
DATA_DIR    = SCRIPT_DIR.parent.parent / "src" / "data"

# Which raw files belong to which exam
RAW_FILE_MAP = {
    'upsc': [
        RAW_DIR / "upsc_raw.json",          # from indiabix_scraper.py
        RAW_DIR / "pyq_upsc_raw.json",      # from pyq_scraper.py
    ],
    'apsc': [
        RAW_DIR / "apsc_raw.json",          # from indiabix_scraper.py
        RAW_DIR / "pyq_apsc_raw.json",      # from pyq_scraper.py
        RAW_DIR / "apsc_web_raw.json",      # from apsc_web_scraper.py
        RAW_DIR / "apsc_telegram_raw.json", # from apsc_telegram_scraper.py
        RAW_DIR / "apsc_pdf_raw.json",      # from apsc_pdf_scraper.py
        RAW_DIR / "gktoday_apsc_raw.json",  # from gktoday_scraper.py
        RAW_DIR / "tg_pdf_raw.json",        # from tg_pdf_downloader.py
        RAW_DIR / "gemini_ocr_raw.json",      # from gemini_ocr_scraper.py
        RAW_DIR / "gemini_apsc_raw.json",   # from gemini_generate.py
        RAW_DIR / "apsc_official_raw.json", # from gemini_ocr_official.py (apsc.nic.in)
        RAW_DIR / "apsc_prelims_raw.json",  # from gemini_ocr_prelims.py (assamcareer.com 1998-2024)
    ],
    'cat': [
        RAW_DIR / "cat_raw.json",
        RAW_DIR / "pyq_cat_raw.json",
        RAW_DIR / "examveda_cat_raw.json",    # from examveda_scraper.py
        RAW_DIR / "cat_mock_tg_raw.json",     # from cat_mock_tg_scraper.py (Telegram mocks)
    ],
}

# Allowed subject values per exam (must match what the frontend uses)
VALID_SUBJECTS = {
    'upsc': {'History', 'Geography', 'Polity', 'Economy', 'Environment', 'Science & Tech'},
    'apsc': {'Assam History', 'Assam Geography', 'Art & Culture', 'History', 'Geography',
             'Polity', 'Economy', 'Environment', 'Science'},
    'cat':  {'Quantitative Aptitude', 'Verbal Ability', 'Data Interpretation', 'Logical Reasoning'},
}

ID_PREFIXES = {'upsc': 'u', 'apsc': 'a', 'cat': 'c'}


def load_raw(exam: str) -> list[dict]:
    """Load and merge all raw files for an exam."""
    all_qs = []
    for path in RAW_FILE_MAP.get(exam, []):
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                qs = json.load(f)
                logger.info(f"  Loaded {len(qs):>5} questions from {path.name}")
                all_qs.extend(qs)
        else:
            logger.info(f"  (Not found: {path.name})")
    return all_qs


def load_existing(exam: str) -> list[dict]:
    """Load current src/data/{exam}.json."""
    path = DATA_DIR / f"{exam}.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def clean_text(text: str) -> str:
    """Normalise whitespace, strip HTML artifacts."""
    text = re.sub(r'<[^>]+>', ' ', text)         # strip any HTML
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('\u00a0', ' ')            # non-breaking space
    return text


def validate_question(q: dict, exam: str) -> tuple[bool, str]:
    """Return (is_valid, reason_if_not)."""
    text = clean_text(q.get('text', ''))
    if len(text) < 10:
        return False, "question too short"

    opts = q.get('options', [])
    if len(opts) < 4:
        return False, f"only {len(opts)} options"

    cleaned_opts = [clean_text(str(o)) for o in opts[:4]]
    if any(len(o) < 1 for o in cleaned_opts):
        return False, "empty option"

    correct = q.get('correct')
    if correct not in (0, 1, 2, 3):
        return False, f"invalid correct index: {correct}"

    subject = q.get('subject', '')
    if subject not in VALID_SUBJECTS.get(exam, set()):
        return False, f"invalid subject: {subject!r}"

    diff = q.get('difficulty', '')
    if diff not in ('easy', 'medium', 'hard'):
        return False, f"invalid difficulty: {diff!r}"

    return True, ''


def deduplicate(questions: list[dict]) -> list[dict]:
    """
    Remove duplicates using:
    1. Exact text match (case-insensitive, stripped)
    2. 80%+ word overlap (near-duplicate questions)
    """
    seen_texts: dict[str, int] = {}
    unique = []

    def normalise(text: str) -> str:
        return re.sub(r'\s+', ' ', text.lower().strip())

    def word_set(text: str) -> set[str]:
        return set(re.findall(r'\b\w{4,}\b', text.lower()))

    for q in questions:
        norm = normalise(q.get('text', ''))
        if norm in seen_texts:
            continue

        # Near-duplicate check (against last 500 for performance)
        wset = word_set(norm)
        is_dup = False
        for prev_norm in list(seen_texts.keys())[-500:]:
            prev_wset = word_set(prev_norm)
            if not prev_wset:
                continue
            overlap = len(wset & prev_wset) / max(len(wset), len(prev_wset), 1)
            if overlap >= 0.80:
                is_dup = True
                break

        if not is_dup:
            seen_texts[norm] = 1
            unique.append(q)

    return unique


def assign_ids(questions: list[dict], exam: str, start: int) -> list[dict]:
    """Assign clean sequential IDs like u160, u161, …"""
    prefix = ID_PREFIXES[exam]
    for i, q in enumerate(questions):
        q['id'] = f"{prefix}{start + i}"
    return questions


def process_exam(exam: str, dry_run: bool = False) -> dict:
    """Full pipeline for one exam. Returns stats dict."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {exam.upper()}")
    logger.info('='*60)

    # 1. Load existing + raw
    existing = load_existing(exam)
    raw      = load_raw(exam)
    logger.info(f"Existing: {len(existing)} | Raw scraped: {len(raw)}")

    existing_texts = {
        re.sub(r'\s+', ' ', q.get('text', '').lower().strip())
        for q in existing
    }

    # 2. Validate raw questions
    valid, invalid = [], 0
    for q in raw:
        ok, reason = validate_question(q, exam)
        if ok:
            norm = re.sub(r'\s+', ' ', q.get('text', '').lower().strip())
            if norm not in existing_texts:
                valid.append(q)
        else:
            invalid += 1
            logger.debug(f"Invalid ({reason}): {str(q.get('text',''))[:60]}")

    logger.info(f"Valid new questions: {len(valid)} | Invalid/skipped: {invalid}")

    # 3. Clean text fields
    for q in valid:
        q['text'] = clean_text(q['text'])
        q['options'] = [clean_text(str(o)) for o in q['options'][:4]]
        q['explanation'] = clean_text(q.get('explanation', ''))
        # Remove scraper-only fields
        for field in ('source', 'year'):
            q.pop(field, None)

    # 4. Deduplicate among new questions
    before_dedup = len(valid)
    valid = deduplicate(valid)
    logger.info(f"After dedup: {len(valid)} (removed {before_dedup - len(valid)} near-dupes)")

    # 5. Assign IDs
    start_id = len(existing) + 1
    valid = assign_ids(valid, exam, start_id)

    # 6. Merge
    merged = existing + valid
    logger.info(f"Final question bank: {len(merged)} questions")

    # Subject breakdown
    from collections import Counter
    subject_counts = Counter(q['subject'] for q in merged)
    for subj, cnt in sorted(subject_counts.items()):
        logger.info(f"  {subj:<30} {cnt:>4}")

    if not dry_run and valid:
        out_path = DATA_DIR / f"{exam}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        logger.info(f"\nSaved → {out_path}")

    return {
        'exam': exam,
        'existing': len(existing),
        'new': len(valid),
        'total': len(merged),
        'subject_counts': dict(subject_counts),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pipeline: raw → src/data JSON')
    parser.add_argument('--exam', choices=['upsc', 'apsc', 'cat', 'all'], default='all')
    parser.add_argument('--stats', action='store_true', help='Dry run: print stats only')
    args = parser.parse_args()

    exams = ['upsc', 'apsc', 'cat'] if args.exam == 'all' else [args.exam]
    results = []
    for exam in exams:
        stats = process_exam(exam, dry_run=args.stats)
        results.append(stats)

    print("\n" + "-"*50)
    print("SUMMARY")
    print("-"*50)
    for r in results:
        action = "(dry run)" if args.stats else "written"
        print(f"{r['exam'].upper():6} {r['existing']:>5} existing + {r['new']:>5} new = {r['total']:>5} total {action}")
