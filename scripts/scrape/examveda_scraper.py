#!/usr/bin/env python3
"""
Examveda Scraper for ExamForge
-------------------------------
Scrapes arithmetic/QA MCQs from examveda.com.
Answers and solutions are embedded in hidden HTML — no JS rendering needed.

Output: raw/examveda_cat_raw.json

Usage:
    python examveda_scraper.py
    python examveda_scraper.py --dry-run     # print counts only, no save
"""

import re
import json
import time
import logging
import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('examveda_cat.log', encoding='utf-8'),
    ]
)
log = logging.getLogger(__name__)

BASE_URL  = 'https://www.examveda.com'
RAW_DIR   = Path(__file__).parent / 'raw'
RAW_DIR.mkdir(exist_ok=True)
OUTPUT    = RAW_DIR / 'examveda_cat_raw.json'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/124.0.0.0 Safari/537.36'),
    'Referer': 'https://www.examveda.com/',
}

# Answer map: hidden input value is 1-indexed (1=A, 2=B, 3=C, 4=D)
ANSWER_MAP = {1: 0, 2: 1, 3: 2, 4: 3}

# ── Topic catalogue ──────────────────────────────────────────────────────────
# (url_slug, subject_label, id_prefix)
QA_TOPICS = [
    ('average',                'Quantitative Aptitude', 'ev-avg'),
    ('percentage',             'Quantitative Aptitude', 'ev-per'),
    ('profit-and-loss',        'Quantitative Aptitude', 'ev-pl'),
    ('compound-interest',      'Quantitative Aptitude', 'ev-ci'),
    ('time-and-work',          'Quantitative Aptitude', 'ev-tw'),
    ('problems-on-numbers',    'Quantitative Aptitude', 'ev-pn'),
    ('problems-on-ages',       'Quantitative Aptitude', 'ev-ages'),
    ('square-root-and-cube-root', 'Quantitative Aptitude', 'ev-sqrt'),
    ('surds-and-indices',      'Quantitative Aptitude', 'ev-surds'),
    ('simplification',         'Quantitative Aptitude', 'ev-simp'),
    ('permutation-and-combination', 'Quantitative Aptitude', 'ev-pc'),
    ('probability',            'Quantitative Aptitude', 'ev-prob'),
    ('area',                   'Quantitative Aptitude', 'ev-area'),
    ('volume-and-surface-area','Quantitative Aptitude', 'ev-vol'),
    ('boats-and-streams',      'Quantitative Aptitude', 'ev-boats'),
    ('pipes-and-cistern',      'Quantitative Aptitude', 'ev-pipes'),
    ('height-and-distance',    'Quantitative Aptitude', 'ev-hd'),
    ('number-system',          'Quantitative Aptitude', 'ev-ns'),
    ('decimal-fraction',       'Quantitative Aptitude', 'ev-df'),
    ('partnership',            'Quantitative Aptitude', 'ev-par'),
    ('calendar',               'Quantitative Aptitude', 'ev-cal'),
]


def fetch(url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return BeautifulSoup(r.text, 'lxml')
            if r.status_code == 404:
                return None
            log.warning(f'HTTP {r.status_code} {url} (attempt {attempt})')
        except requests.RequestException as e:
            log.warning(f'Request error {url}: {e} (attempt {attempt})')
        if attempt < retries:
            time.sleep(3 * attempt)
    return None


def parse_page(soup: BeautifulSoup, subject: str, prefix: str) -> list[dict]:
    questions = []
    articles = soup.find_all('article', class_='single-question')

    for art in articles:
        try:
            # Question text
            q_div = art.find('div', class_='question-main')
            if not q_div:
                continue
            q_text = q_div.get_text(separator=' ', strip=True)
            if len(q_text) < 10:
                continue

            # Options — labels paired with radio inputs
            opts = []
            for p in art.find_all('p'):
                labels = p.find_all('label')
                # Each option has two labels: letter + text
                # Letter label has style attr, text label doesn't
                text_labels = [l for l in labels if not l.get('style')]
                if text_labels:
                    opts.append(text_labels[-1].get_text(separator=' ', strip=True))
            if len(opts) < 4:
                continue
            opts = opts[:4]

            # Correct answer — hidden input with no name, value 1-4
            hidden = art.find('input', type='hidden')
            if not hidden or not hidden.get('value'):
                continue
            try:
                raw_val = int(hidden['value'].strip())
            except ValueError:
                continue
            correct = ANSWER_MAP.get(raw_val)
            if correct is None:
                continue

            # Explanation — in hidden answer_container div
            explanation = ''
            ans_div = art.find('div', class_='answer_container')
            if ans_div:
                # Remove the "Answer: Option X" header part
                sol_spans = ans_div.find_all('span', class_='color')
                for sp in sol_spans:
                    if 'Solution' in sp.get_text():
                        parent = sp.parent
                        # get sibling text
                        explanation = parent.get_text(separator=' ', strip=True)
                        explanation = re.sub(r'^Solution\s*:?\s*', '', explanation).strip()
                        break
                # Fallback: strip "Answer: Option X" and take the rest
                if not explanation:
                    full = ans_div.get_text(separator=' ', strip=True)
                    full = re.sub(r'Answer\s*&\s*Solution', '', full, flags=re.I)
                    full = re.sub(r'Answer\s*:\s*Option\s*[A-D]', '', full, flags=re.I)
                    full = re.sub(r'Solution\s*:', '', full, flags=re.I).strip()
                    if len(full) > 10:
                        explanation = full

            # Clean up MathJax artifacts
            explanation = re.sub(r'\$\$.*?\$\$', '', explanation, flags=re.DOTALL).strip()
            explanation = re.sub(r'\s+', ' ', explanation).strip()

            # Unique ID from hidden input id (format "answer_N")
            ans_id = hidden.get('id', '').replace('answer_', '')
            uid = f'{prefix}-{ans_id}' if ans_id else f'{prefix}-{len(questions)}'

            questions.append({
                'id':          uid,
                'subject':     subject,
                'difficulty':  'medium',
                'text':        q_text,
                'options':     opts,
                'correct':     correct,
                'explanation': explanation,
                'source':      'examveda',
            })
        except Exception as e:
            log.debug(f'Parse error: {e}')

    return questions


def scrape_topic(slug: str, subject: str, prefix: str) -> list[dict]:
    base = f'{BASE_URL}/arithmetic-ability/practice-mcq-question-on-{slug}/'
    all_qs = []

    # Section 1 (no param) — also find how many sections exist
    soup = fetch(base)
    if not soup:
        log.warning(f'  Skipping {slug} (fetch failed)')
        return []

    page_qs = parse_page(soup, subject, f'{prefix}-s1')
    all_qs.extend(page_qs)

    # Find section links
    section_links = [a['href'] for a in soup.find_all('a', href=True)
                     if 'section=' in a.get('href', '')]
    # Extract max section number
    max_sec = 1
    for href in section_links:
        m = re.search(r'section=(\d+)', href)
        if m:
            max_sec = max(max_sec, int(m.group(1)))

    # Fetch remaining sections
    for sec in range(2, max_sec + 1):
        time.sleep(0.4)
        sec_soup = fetch(f'{base}?section={sec}')
        if not sec_soup:
            continue
        sec_qs = parse_page(sec_soup, subject, f'{prefix}-s{sec}')
        all_qs.extend(sec_qs)

    log.info(f'  {slug}: {len(all_qs)} questions ({max_sec} sections)')
    return all_qs


def main(dry_run: bool = False):
    # Load existing
    existing = []
    if OUTPUT.exists():
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    existing_ids = {q['id'] for q in existing}
    log.info(f'Existing: {len(existing)} examveda questions')

    all_new = []
    for slug, subject, prefix in QA_TOPICS:
        time.sleep(0.5)
        qs = scrape_topic(slug, subject, prefix)
        new_qs = [q for q in qs if q['id'] not in existing_ids]
        for q in new_qs:
            existing_ids.add(q['id'])
        all_new.extend(new_qs)

    log.info(f'\nNew questions scraped: {len(all_new)}')

    if not dry_run:
        combined = existing + all_new
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        log.info(f'Saved {len(combined)} total → {OUTPUT}')
    else:
        log.info('Dry run — not saving')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    main(dry_run=args.dry_run)
