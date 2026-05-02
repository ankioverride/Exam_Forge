#!/usr/bin/env python3
"""
IndiaBix Scraper for ExamForge
-------------------------------
Scrapes MCQ questions from IndiaBix.com for UPSC, CAT, and APSC-relevant subjects.
Output: raw JSON files in scripts/scrape/raw/ — run pipeline.py afterwards to merge into src/data/.

Usage:
    python indiabix_scraper.py --exam upsc
    python indiabix_scraper.py --exam cat
    python indiabix_scraper.py --exam apsc
    python indiabix_scraper.py --exam all
    python indiabix_scraper.py --exam upsc --max-pages 5   # limit pages per category (for testing)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
import argparse
import random
import logging
from pathlib import Path
from urllib.parse import urljoin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scrape.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.indiabix.com"
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.indiabix.com/',
    'DNT': '1',
}

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

# ─── Category definitions ─────────────────────────────────────────────────────
# Format: url_path → (subject label, short_prefix_for_id)

UPSC_CATEGORIES = {
    '/general-knowledge/indian-history/':            ('History',       'ib-ih'),
    '/general-knowledge/indian-geography/':          ('Geography',     'ib-ig'),
    '/general-knowledge/indian-politics/':           ('Polity',        'ib-ip'),
    '/general-knowledge/indian-economy/':            ('Economy',       'ib-ie'),
    '/general-knowledge/general-science/':           ('Science & Tech','ib-gs'),
    '/general-knowledge/biology/':                   ('Science & Tech','ib-bi'),
    '/general-knowledge/physics/':                   ('Science & Tech','ib-ph'),
    '/general-knowledge/chemistry/':                 ('Science & Tech','ib-ch'),
    '/general-knowledge/world-geography/':           ('Geography',     'ib-wg'),
    '/general-knowledge/environment-and-ecology/':   ('Environment',   'ib-ee'),
    '/general-knowledge/basic-general-knowledge/':   ('History',       'ib-bg'),
    '/general-knowledge/indian-culture/':            ('History',       'ib-ic'),
    '/general-knowledge/inventions/':               ('Science & Tech','ib-iv'),
    '/general-knowledge/famous-personalities/':      ('History',       'ib-fp'),
    '/general-knowledge/books-and-authors/':         ('History',       'ib-ba'),
    '/general-knowledge/awards-and-honors/':         ('History',       'ib-ah'),
    '/general-knowledge/sports/':                    ('History',       'ib-sp'),
    '/general-knowledge/technology/':                ('Science & Tech','ib-te'),
}

CAT_CATEGORIES = {
    # Verbal Ability
    '/verbal-ability/synonyms/':                     ('Verbal Ability',      'ib-vs'),
    '/verbal-ability/antonyms/':                     ('Verbal Ability',      'ib-va'),
    '/verbal-ability/sentence-correction/':          ('Verbal Ability',      'ib-sc'),
    '/verbal-ability/ordering-of-sentences/':        ('Verbal Ability',      'ib-os'),
    '/verbal-ability/spotting-errors/':              ('Verbal Ability',      'ib-spe'),
    '/verbal-ability/selecting-words/':              ('Verbal Ability',      'ib-sw'),
    '/verbal-ability/comprehension/':                ('Verbal Ability',      'ib-vc'),
    '/verbal-ability/fill-in-the-blanks/':           ('Verbal Ability',      'ib-fb'),
    '/verbal-ability/sentence-improvement/':         ('Verbal Ability',      'ib-si'),
    '/verbal-ability/change-of-voice/':              ('Verbal Ability',      'ib-cv'),
    '/verbal-ability/idioms-and-phrases/':           ('Verbal Ability',      'ib-ip2'),
    # Logical Reasoning
    '/logical-reasoning/number-series/':             ('Logical Reasoning',   'ib-ns'),
    '/logical-reasoning/letter-and-symbol-series/':  ('Logical Reasoning',   'ib-ls'),
    '/logical-reasoning/logical-problems/':          ('Logical Reasoning',   'ib-lp'),
    '/logical-reasoning/seating-arrangement/':       ('Logical Reasoning',   'ib-sea'),
    '/logical-reasoning/blood-relation-test/':       ('Logical Reasoning',   'ib-br'),
    '/logical-reasoning/syllogism/':                 ('Logical Reasoning',   'ib-sy'),
    '/logical-reasoning/direction-sense-test/':      ('Logical Reasoning',   'ib-dst'),
    '/logical-reasoning/coding-decoding/':           ('Logical Reasoning',   'ib-cd'),
    '/logical-reasoning/odd-man-out/':               ('Logical Reasoning',   'ib-om'),
    '/logical-reasoning/analogies/':                 ('Logical Reasoning',   'ib-an'),
    '/logical-reasoning/classification/':            ('Logical Reasoning',   'ib-cl'),
    '/logical-reasoning/statements-and-conclusions/':('Logical Reasoning',   'ib-stc'),
    '/logical-reasoning/statements-and-assumptions/':('Logical Reasoning',   'ib-sta'),
    '/logical-reasoning/statements-and-arguments/':  ('Logical Reasoning',   'ib-starg'),
    '/logical-reasoning/cause-and-effect/':          ('Logical Reasoning',   'ib-ce'),
    # Data Interpretation
    '/data-interpretation/bar-charts/':              ('Data Interpretation', 'ib-dc'),
    '/data-interpretation/pie-charts/':              ('Data Interpretation', 'ib-dp'),
    '/data-interpretation/line-charts/':             ('Data Interpretation', 'ib-dl'),
    '/data-interpretation/table-charts/':            ('Data Interpretation', 'ib-dt'),
    # Quantitative Aptitude
    '/arithmetic/problems-on-numbers/':              ('Quantitative Aptitude','ib-pn'),
    '/arithmetic/problems-on-h-c-f-and-l-c-m/':     ('Quantitative Aptitude','ib-hcf'),
    '/arithmetic/decimal-fractions/':                ('Quantitative Aptitude','ib-df'),
    '/arithmetic/percentage/':                       ('Quantitative Aptitude','ib-per'),
    '/arithmetic/profit-and-loss/':                  ('Quantitative Aptitude','ib-pl'),
    '/arithmetic/simple-interest/':                  ('Quantitative Aptitude','ib-sii'),
    '/arithmetic/compound-interest/':                ('Quantitative Aptitude','ib-ci'),
    '/arithmetic/time-and-work/':                    ('Quantitative Aptitude','ib-tw'),
    '/arithmetic/time-and-distance/':                ('Quantitative Aptitude','ib-td'),
    '/arithmetic/problems-on-trains/':               ('Quantitative Aptitude','ib-pt'),
    '/arithmetic/mixtures-and-alligations/':         ('Quantitative Aptitude','ib-mix'),
    '/arithmetic/ratio-and-proportion/':             ('Quantitative Aptitude','ib-rp'),
    '/arithmetic/partnership/':                      ('Quantitative Aptitude','ib-par'),
    '/arithmetic/average/':                          ('Quantitative Aptitude','ib-avg'),
    '/arithmetic/permutation-and-combination/':      ('Quantitative Aptitude','ib-pc'),
    '/arithmetic/probability/':                      ('Quantitative Aptitude','ib-prob'),
    '/arithmetic/area/':                             ('Quantitative Aptitude','ib-area'),
    '/arithmetic/volume-and-surface-area/':          ('Quantitative Aptitude','ib-vol'),
    '/arithmetic/pipes-and-cistern/':                ('Quantitative Aptitude','ib-pipes'),
    '/arithmetic/boats-and-streams/':                ('Quantitative Aptitude','ib-boats'),
    '/arithmetic/problems-on-ages/':                 ('Quantitative Aptitude','ib-ages'),
}

# For APSC we reuse UPSC GK + Assam-specific
APSC_CATEGORIES = {
    '/general-knowledge/indian-history/':            ('History',        'ib-ih'),
    '/general-knowledge/indian-geography/':          ('Geography',      'ib-ig'),
    '/general-knowledge/indian-politics/':           ('Polity',         'ib-ip'),
    '/general-knowledge/indian-economy/':            ('Economy',        'ib-ie'),
    '/general-knowledge/general-science/':           ('Science',        'ib-gs'),
    '/general-knowledge/environment-and-ecology/':   ('Environment',    'ib-ee'),
}

EXAM_CATEGORIES = {
    'upsc': UPSC_CATEGORIES,
    'cat':  CAT_CATEGORIES,
    'apsc': APSC_CATEGORIES,
}


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)

def fetch(url: str, retries: int = 3) -> BeautifulSoup | None:
    """Fetch a URL and return BeautifulSoup, with retry on failure."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'lxml')
            elif resp.status_code == 404:
                logger.warning(f"404 Not Found: {url}")
                return None
            else:
                logger.warning(f"HTTP {resp.status_code} on {url}, attempt {attempt}")
        except requests.RequestException as e:
            logger.warning(f"Request error on {url}: {e}, attempt {attempt}")
        if attempt < retries:
            time.sleep(3 * attempt)
    return None


# ─── Parsing ─────────────────────────────────────────────────────────────────

def parse_questions(soup: BeautifulSoup, subject: str, prefix: str) -> list[dict]:
    """Extract all questions from a BeautifulSoup page."""
    questions = []
    containers = soup.find_all('div', class_='bix-div-container')

    for container in containers:
        try:
            # Question text
            qtxt_div = container.find('div', class_='bix-td-qtxt')
            if not qtxt_div:
                continue
            q_text = qtxt_div.get_text(separator=' ', strip=True)
            if not q_text or len(q_text) < 10:
                continue

            # Options
            opt_rows = container.find_all('div', class_='bix-opt-row')
            if len(opt_rows) < 4:
                continue
            options = []
            for row in opt_rows[:4]:
                val_div = row.find('div', class_='bix-td-option-val')
                if val_div:
                    inner = val_div.find('div', class_='flex-wrap')
                    opt_text = (inner or val_div).get_text(separator=' ', strip=True)
                    options.append(opt_text)

            if len(options) < 4 or any(not o for o in options):
                continue

            # Correct answer (hidden input with letter A/B/C/D)
            hidden = container.find('input', class_='jq-hdnakq')
            if not hidden or not hidden.get('value'):
                continue
            answer_letter = hidden['value'].strip().upper()
            correct_idx = ANSWER_MAP.get(answer_letter)
            if correct_idx is None:
                continue

            # Explanation
            ans_div = container.find('div', class_='bix-div-answer')
            explanation = ''
            if ans_div:
                desc = ans_div.find('div', class_='bix-ans-description')
                if desc:
                    # Remove Wikipedia links text but keep rest
                    for a in desc.find_all('a'):
                        a.decompose()
                    explanation = desc.get_text(separator=' ', strip=True)
                    # Clean up common filler text
                    if 'Let\'s discuss' in explanation or len(explanation) < 5:
                        explanation = ''

            # Derive difficulty heuristic from question length + option complexity
            difficulty = _infer_difficulty(q_text, options)

            # Unique ID based on hidden input ID
            qid_raw = hidden.get('id', '').replace('hdnAnswer_', '')
            uid = f"{prefix}-{qid_raw}" if qid_raw else f"{prefix}-{len(questions)}"

            questions.append({
                'id':          uid,
                'subject':     subject,
                'difficulty':  difficulty,
                'text':        q_text,
                'options':     options,
                'correct':     correct_idx,
                'explanation': explanation,
                'source':      'indiabix',
            })

        except Exception as e:
            logger.debug(f"Skipped a question due to: {e}")
            continue

    return questions


def _infer_difficulty(text: str, options: list[str]) -> str:
    """Heuristic: longer questions with close options → harder."""
    text_len = len(text)
    avg_opt_len = sum(len(o) for o in options) / 4
    if text_len > 300 or avg_opt_len > 60:
        return 'hard'
    elif text_len > 150 or avg_opt_len > 30:
        return 'medium'
    return 'easy'


def get_all_page_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Collect all pagination URLs for a category (including page 1 = base_url)."""
    urls = [base_url]
    pagination = soup.find('ul', class_='pagination')
    if not pagination:
        return urls
    seen = {base_url}
    for a in pagination.find_all('a', class_='page-link'):
        href = a.get('href', '')
        if href and href != '#' and 'GotoPageModal' not in href:
            full = href if href.startswith('http') else urljoin(BASE_URL, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
    return sorted(set(urls))


# ─── Main scraper ─────────────────────────────────────────────────────────────

def scrape_category(
    url_path: str,
    subject: str,
    prefix: str,
    max_pages: int = 0,
    checkpoint_file: Path = None,
) -> list[dict]:
    """Scrape all pages of one IndiaBix category. Returns list of question dicts."""

    # Load checkpoint if exists
    all_questions = []
    scraped_urls: set[str] = set()
    if checkpoint_file and checkpoint_file.exists():
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_questions = data.get('questions', [])
            scraped_urls = set(data.get('scraped_urls', []))
        logger.info(f"Resumed from checkpoint: {len(all_questions)} questions, {len(scraped_urls)} pages done")

    start_url = urljoin(BASE_URL, url_path)
    logger.info(f"Fetching category: {start_url}")

    soup = fetch(start_url)
    if not soup:
        logger.error(f"Failed to load category page: {start_url}")
        return all_questions

    page_urls = get_all_page_urls(soup, start_url)
    logger.info(f"  Found {len(page_urls)} pages for {subject} ({url_path})")

    if max_pages > 0:
        page_urls = page_urls[:max_pages]

    for i, page_url in enumerate(page_urls):
        if page_url in scraped_urls:
            logger.info(f"  [{i+1}/{len(page_urls)}] Already scraped: {page_url}")
            continue

        logger.info(f"  [{i+1}/{len(page_urls)}] Scraping: {page_url}")

        if i > 0 or page_url != start_url:
            page_soup = fetch(page_url)
        else:
            page_soup = soup

        if not page_soup:
            logger.warning(f"  Failed to fetch: {page_url}")
            continue

        qs = parse_questions(page_soup, subject, prefix)
        all_questions.extend(qs)
        scraped_urls.add(page_url)
        logger.info(f"    Extracted {len(qs)} questions (total: {len(all_questions)})")

        # Save checkpoint after each page
        if checkpoint_file:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({'questions': all_questions, 'scraped_urls': list(scraped_urls)}, f, ensure_ascii=False)

        # Polite delay: 1.5–3.5 seconds between pages
        time.sleep(random.uniform(1.5, 3.5))

    return all_questions


def scrape_exam(exam: str, max_pages: int = 0) -> None:
    """Scrape all categories for an exam and save raw output."""
    categories = EXAM_CATEGORIES.get(exam)
    if not categories:
        logger.error(f"Unknown exam: {exam}")
        return

    output_file = RAW_DIR / f"{exam}_raw.json"
    all_questions: list[dict] = []

    # Load existing raw output to resume
    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        logger.info(f"Loaded {len(all_questions)} existing questions for {exam}")

    existing_ids = {q['id'] for q in all_questions}

    for url_path, (subject, prefix) in categories.items():
        cp_file = RAW_DIR / f"checkpoint_{exam}_{prefix.replace('/', '_')}.json"
        logger.info(f"\n{'='*60}")
        logger.info(f"Category: {subject} | {url_path}")

        cat_questions = scrape_category(url_path, subject, prefix, max_pages, cp_file)

        # Merge, skipping duplicates
        new_qs = [q for q in cat_questions if q['id'] not in existing_ids]
        all_questions.extend(new_qs)
        existing_ids.update(q['id'] for q in new_qs)

        logger.info(f"Added {len(new_qs)} new questions. Grand total: {len(all_questions)}")

        # Save after each category
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=2)

        # Extra pause between categories
        time.sleep(random.uniform(3, 6))

    logger.info(f"\nDone! {len(all_questions)} questions saved to {output_file}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IndiaBix Question Scraper')
    parser.add_argument(
        '--exam', choices=['upsc', 'cat', 'apsc', 'all'],
        default='all', help='Which exam to scrape'
    )
    parser.add_argument(
        '--max-pages', type=int, default=0,
        help='Max pages per category (0 = all). Use 2-3 for testing.'
    )
    args = parser.parse_args()

    exams = ['upsc', 'cat', 'apsc'] if args.exam == 'all' else [args.exam]
    for exam in exams:
        logger.info(f"\n{'#'*60}")
        logger.info(f"  SCRAPING: {exam.upper()}")
        logger.info(f"{'#'*60}")
        scrape_exam(exam, args.max_pages)
