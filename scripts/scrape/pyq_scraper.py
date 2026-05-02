#!/usr/bin/env python3
"""
PYQ Scraper for ExamForge
--------------------------
Scrapes Previous Year Questions (PYQs) from:
  - GKToday.in  → UPSC Prelims GS-1 papers (year-wise)
  - 2IIM.com    → CAT previous year papers (static HTML)
  - FreePYQ     → APSC PYQ questions

Output: raw JSON in scripts/scrape/raw/pyq_<exam>.json
Run pipeline.py afterwards to merge into src/data/.

Usage:
    python pyq_scraper.py --exam upsc
    python pyq_scraper.py --exam cat
    python pyq_scraper.py --exam apsc
    python pyq_scraper.py --exam all
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import argparse
import logging
import random
from pathlib import Path
from urllib.parse import urljoin, urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scrape_pyq.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

session = requests.Session()
session.headers.update(HEADERS)

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'a': 0, 'b': 1, 'c': 2, 'd': 3}


def fetch(url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=25)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'lxml')
            elif resp.status_code in (403, 404, 410):
                logger.warning(f"HTTP {resp.status_code}: {url}")
                return None
            logger.warning(f"HTTP {resp.status_code} attempt {attempt}: {url}")
        except requests.RequestException as e:
            logger.warning(f"Request error attempt {attempt}: {e}")
        time.sleep(3 * attempt)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# GKToday — UPSC Prelims PYQs
# ═══════════════════════════════════════════════════════════════════════════════

# GKToday hosts UPSC Prelims papers in a quiz format.
# URL pattern: /quizbase/upsc-civil-services-prelims-{YEAR}-general-studies-paper-1/

GKTODAY_UPSC_YEARS = list(range(2010, 2025))  # 2010–2024

GKTODAY_UPSC_URL_PATTERNS = [
    "https://www.gktoday.in/quizbase/upsc-civil-services-prelims-{year}-general-studies-paper-1/",
    "https://www.gktoday.in/quizbase/ias-prelims-{year}-general-studies-paper-i/",
    "https://gktoday.in/quizbase/upsc-prelims-{year}-gs-paper-1/",
]

# Subject classification keywords (for auto-tagging PYQs)
SUBJECT_KEYWORDS = {
    'History':       ['mughal','british','colonial','revolt','gandhi','nehru','congress','maurya',
                      'medieval','ancient','indus','vedic','maratha','sultan','empire','dynasty',
                      'freedom','independence','partition','1857','treaty','war of','battle of',
                      'french revolution','world war','cold war'],
    'Geography':     ['river','mountain','plateau','valley','soil','monsoon','rainfall','climate',
                      'desert','coast','peninsula','island','glacier','delta','estuary','gulf',
                      'tropic','latitude','longitude','ocean','sea','pass','strait','dam',
                      'watershed','tributar','drainage','cyclone','earthquake','volcano'],
    'Polity':        ['constitution','article','amendment','parliament','lok sabha','rajya sabha',
                      'president','prime minister','governor','supreme court','high court',
                      'fundamental rights','directive principle','preamble','election','schedule',
                      'judiciary','executive','legislature','bill','act','ordinance','panchayat',
                      'municipality','emergency','finance commission','upsc','election commission'],
    'Economy':       ['gdp','inflation','fiscal','monetary','rbi','sebi','nabard','bank','interest',
                      'poverty','unemployment','budget','tax','gst','trade','import','export',
                      'five year plan','planning commission','niti aayog','subsidy','microfinance',
                      'stock market','bond','mgnrega','pm-kisan','insurance','irdai','npa'],
    'Environment':   ['biodiversity','ecosystem','forest','wildlife','national park','biosphere',
                      'endangered','species','climate change','greenhouse','carbon','ozone',
                      'pollution','ramsar','cites','iucn','kyoto','paris agreement','convention',
                      'tiger','elephant','rhino','mangrove','wetland','coral','migratory'],
    'Science & Tech':['atom','molecule','nuclear','space','isro','satellite','rocket','mission',
                      'chandrayaan','mangalyaan','disease','vaccine','virus','bacteria','dna',
                      'gene','cell','energy','force','gravity','light','sound','electromagnetic',
                      'computer','internet','artificial intelligence','blockchain','5g','nanotechnology'],
}

def classify_subject(text: str) -> str:
    text_lower = text.lower()
    scores = {subj: 0 for subj in SUBJECT_KEYWORDS}
    for subj, keywords in SUBJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[subj] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'History'  # default


def parse_gktoday_quiz(soup: BeautifulSoup, year: int) -> list[dict]:
    """Parse GKToday quiz page. They use a WordPress quiz plugin with standard structure."""
    questions = []

    # Try multiple possible HTML structures
    # Structure 1: div.quiz-question-box
    containers = soup.find_all('div', class_=re.compile(r'quiz.*question|question.*box', re.I))

    # Structure 2: numbered question sections
    if not containers:
        containers = soup.find_all(['div', 'section'], attrs={'class': re.compile(r'question', re.I)})

    # Structure 3: ol/ul with li items (some GKToday pages)
    if not containers:
        # Look for patterns like "1." or "Q1." text
        raw_text = soup.get_text()
        return _parse_text_questions(raw_text, year, 'upsc')

    for i, container in enumerate(containers):
        try:
            text_el = container.find(class_=re.compile(r'quiz.?question|qtxt|question.?text', re.I))
            q_text = (text_el or container).get_text(separator=' ', strip=True)
            q_text = re.sub(r'^Q?\d+[\.\)]\s*', '', q_text).strip()
            if len(q_text) < 15:
                continue

            # Find options
            opt_els = container.find_all(class_=re.compile(r'option|answer.?choice|choice', re.I))
            options = [el.get_text(strip=True) for el in opt_els[:4]]

            # Correct answer
            correct_el = container.find(class_=re.compile(r'correct|right.?answer', re.I))
            correct_text = correct_el.get_text(strip=True) if correct_el else ''
            correct_letter = re.search(r'\b([ABCD])\b', correct_text)
            correct_idx = ANSWER_MAP.get(correct_letter.group(1)) if correct_letter else None

            if not options or len(options) < 4 or correct_idx is None:
                continue

            # Explanation
            exp_el = container.find(class_=re.compile(r'explanation|explain|description', re.I))
            explanation = exp_el.get_text(separator=' ', strip=True) if exp_el else ''

            subject = classify_subject(q_text)
            difficulty = 'medium'  # PYQs are generally medium

            questions.append({
                'id':          f"gkt-upsc{year}-{i+1}",
                'subject':     subject,
                'difficulty':  difficulty,
                'text':        q_text,
                'options':     options,
                'correct':     correct_idx,
                'explanation': explanation,
                'source':      f'gktoday-upsc-{year}',
                'year':        year,
            })
        except Exception as e:
            logger.debug(f"Skip question: {e}")

    return questions


def _parse_text_questions(text: str, year: int, exam: str) -> list[dict]:
    """
    Fallback: parse raw text for numbered MCQ questions.
    Handles common patterns like:
      1. Question text
      (a) option A  (b) option B  (c) option C  (d) option D
      Answer: (b)
    """
    questions = []
    # Pattern: number. question text, then options on same/next lines
    pattern = re.compile(
        r'(\d+)\.\s+(.+?)\n'                          # Q number and text
        r'(?:\([Aa]\)\s*(.+?)\s*(?:\([Bb]\)|\n))'     # option A
        r'(?:\([Bb]\)\s*(.+?)\s*(?:\([Cc]\)|\n))'     # option B
        r'(?:\([Cc]\)\s*(.+?)\s*(?:\([Dd]\)|\n))'     # option C
        r'(?:\([Dd]\)\s*(.+?)(?:\n|$))',               # option D
        re.DOTALL
    )
    ans_pattern = re.compile(r'[Aa]nswer\s*[:\-]?\s*[\(\[]?([ABCDabcd])[\)\]]?')

    for m in pattern.finditer(text):
        try:
            qnum = int(m.group(1))
            q_text = m.group(2).strip()
            opts = [m.group(i).strip() for i in range(3, 7)]

            # Find answer in nearby text
            nearby = text[m.start():m.start()+400]
            ans_match = ans_pattern.search(nearby)
            correct_idx = ANSWER_MAP.get(ans_match.group(1).upper()) if ans_match else None

            if len(q_text) < 10 or not all(opts) or correct_idx is None:
                continue

            questions.append({
                'id':          f"txt-{exam}{year}-{qnum}",
                'subject':     classify_subject(q_text),
                'difficulty':  'medium',
                'text':        q_text,
                'options':     opts,
                'correct':     correct_idx,
                'explanation': '',
                'source':      f'text-{exam}-{year}',
                'year':        year,
            })
        except Exception:
            continue
    return questions


def scrape_upsc_pyqs() -> list[dict]:
    """Scrape UPSC PYQs from GKToday for all available years."""
    all_questions = []
    output_file = RAW_DIR / "pyq_upsc_raw.json"

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        logger.info(f"Loaded {len(all_questions)} existing UPSC PYQs")

    done_years = {q.get('year') for q in all_questions if q.get('year')}

    for year in GKTODAY_UPSC_YEARS:
        if year in done_years:
            logger.info(f"UPSC {year}: already scraped")
            continue

        logger.info(f"\nScraping UPSC PYQ {year}...")
        year_qs = []

        for url_pattern in GKTODAY_UPSC_URL_PATTERNS:
            url = url_pattern.format(year=year)
            soup = fetch(url)
            if soup:
                qs = parse_gktoday_quiz(soup, year)
                if qs:
                    logger.info(f"  {url}: {len(qs)} questions")
                    year_qs.extend(qs)
                    break  # Got questions, no need to try other patterns
            time.sleep(random.uniform(1.5, 3.0))

        if year_qs:
            all_questions.extend(year_qs)
            logger.info(f"  UPSC {year}: {len(year_qs)} questions added")
        else:
            logger.warning(f"  UPSC {year}: no questions found")

        # Save after each year
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=2)

        time.sleep(random.uniform(2, 4))

    logger.info(f"\nUPSC PYQs total: {len(all_questions)}")
    return all_questions


# ═══════════════════════════════════════════════════════════════════════════════
# 2IIM.com — CAT PYQs (static HTML, no JS required)
# ═══════════════════════════════════════════════════════════════════════════════

# 2IIM provides CAT previous year questions with solutions on static pages.
CAT_2IIM_URLS = [
    # CAT QA PYQ pages
    "https://2iim.com/cat-previous-year-questions/cat-quant/",
    "https://2iim.com/cat-previous-year-questions/cat-verbal/",
    "https://2iim.com/cat-previous-year-questions/cat-lrdi/",
    "https://2iim.com/cat-previous-year-questions/",
]

# Cracku — static listing pages (do NOT load question content via JS on listing pages)
CAT_CRACKU_LISTING = "https://cracku.in/cat-previous-year-papers"

CAT_YEARS = list(range(2010, 2025))

# CAT subject mapping based on section
CAT_SECTION_MAP = {
    'quant': 'Quantitative Aptitude',
    'verbal': 'Verbal Ability',
    'varc': 'Verbal Ability',
    'lrdi': 'Data Interpretation',
    'di': 'Data Interpretation',
    'lr': 'Logical Reasoning',
}


def parse_2iim_page(soup: BeautifulSoup, section: str, year: int, base_id: str) -> list[dict]:
    """Parse a 2IIM CAT question page."""
    questions = []
    subject = CAT_SECTION_MAP.get(section.lower(), 'Quantitative Aptitude')

    # 2IIM question structure: each question in a div/section
    containers = soup.find_all(['div', 'article'], class_=re.compile(r'question|quiz|exercise', re.I))
    if not containers:
        # Fallback: look for numbered questions in text
        text = soup.get_text()
        return _parse_text_questions(text, year, 'cat')

    for i, container in enumerate(containers):
        try:
            # Question text
            q_paras = container.find_all('p')
            if not q_paras:
                continue
            q_text = q_paras[0].get_text(separator=' ', strip=True)
            if len(q_text) < 10:
                continue

            # Find options (usually labeled A/B/C/D or 1/2/3/4)
            option_els = container.find_all(string=re.compile(r'^\s*[ABCD1-4][\.\)]\s+.{3,}'))
            options = []
            for el in option_els[:4]:
                opt = re.sub(r'^\s*[ABCD1-4][\.\)]\s*', '', str(el)).strip()
                if opt:
                    options.append(opt)

            if len(options) < 4:
                continue

            # Answer
            ans_el = container.find(string=re.compile(r'answer\s*[:\-]?\s*[ABCD1-4]', re.I))
            correct_idx = None
            if ans_el:
                m = re.search(r'[ABCD]', ans_el, re.I)
                correct_idx = ANSWER_MAP.get(m.group().upper()) if m else None

            if correct_idx is None:
                continue

            # Explanation
            exp_el = container.find(class_=re.compile(r'solution|explanation|explain', re.I))
            explanation = exp_el.get_text(separator=' ', strip=True) if exp_el else ''

            questions.append({
                'id':          f"{base_id}-{i+1}",
                'subject':     subject,
                'difficulty':  'medium',
                'text':        q_text,
                'options':     options,
                'correct':     correct_idx,
                'explanation': explanation,
                'source':      f'2iim-cat-{year}',
                'year':        year,
            })
        except Exception as e:
            logger.debug(f"Skip: {e}")

    return questions


def scrape_cat_pyqs() -> list[dict]:
    """Scrape CAT PYQs from 2IIM."""
    all_questions = []
    output_file = RAW_DIR / "pyq_cat_raw.json"

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        logger.info(f"Loaded {len(all_questions)} existing CAT PYQs")

    existing_ids = {q['id'] for q in all_questions}

    for i, url in enumerate(CAT_2IIM_URLS):
        logger.info(f"\nFetching CAT source: {url}")
        soup = fetch(url)
        if not soup:
            continue

        # Find all question page links
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '2iim.com' in href or href.startswith('/'):
                if any(kw in href for kw in ['question', 'cat-20', 'pyq', 'previous']):
                    full = href if href.startswith('http') else urljoin("https://2iim.com", href)
                    links.append(full)

        logger.info(f"  Found {len(links)} question page links")

        for j, link in enumerate(links[:200]):  # cap per source
            year_match = re.search(r'20(\d{2})', link)
            year = int('20' + year_match.group(1)) if year_match else 2020

            section = 'quant'
            for key in CAT_SECTION_MAP:
                if key in link.lower():
                    section = key
                    break

            base_id = f"2iim-{section}-{year}-{j}"
            if base_id + "-1" in existing_ids:
                continue

            page_soup = fetch(link)
            if not page_soup:
                time.sleep(1)
                continue

            qs = parse_2iim_page(page_soup, section, year, base_id)
            new_qs = [q for q in qs if q['id'] not in existing_ids]
            all_questions.extend(new_qs)
            existing_ids.update(q['id'] for q in new_qs)

            if new_qs:
                logger.info(f"  [{j+1}] {link}: +{len(new_qs)} questions")

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_questions, f, ensure_ascii=False, indent=2)

            time.sleep(random.uniform(1.5, 3.0))

    logger.info(f"\nCAT PYQs total: {len(all_questions)}")
    return all_questions


# ═══════════════════════════════════════════════════════════════════════════════
# APSC PYQs — Assam-specific sources
# ═══════════════════════════════════════════════════════════════════════════════

APSC_SOURCES = [
    "https://www.gktoday.in/quizbase/assam-general-knowledge-questions/",
    "https://www.gktoday.in/quizbase/assam-history-gk-questions/",
    "https://www.gktoday.in/quizbase/assam-geography-gk-quiz/",
    "https://www.indiabix.com/general-knowledge/assam/",
    "https://www.indiabix.com/general-knowledge/north-east-india/",
]

APSC_SUBJECT_KEYWORDS = {
    'Assam History':   ['ahom','assam','lachit','saraighat','mughal','british assam','yandabo',
                        'burmese','borphukan','guwahati','dispur','sukaphaa','maniram','moamoriya',
                        'koch kingdom','kachari','chutia','assam accord'],
    'Assam Geography': ['brahmaputra','barak','kaziranga','manas','assam district','majuli',
                        'kopili','subansiri','lohit','dibrugarh','tinsukia','kamrup','nagaon',
                        'karbi anglong','golaghat','jorhat','sibsagar','sibasagar'],
    'Art & Culture':   ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi',
                        'ankiya naat','bhaona','ojapali','kamakhya','vaishnavite','satra',
                        'rongali','kongali','bhogali','dhol','pepa','zikir','zari'],
    'Polity':          ['sixth schedule','bodoland','assam accord','nrc','imdt','article 371',
                        'assam legislative','gauhati high court','btc','karbi council'],
    'Economy':         ['digboi','oil india','numaligarh','ongc','tea assam','assam tea',
                        'brahmaputra cracker','bhel bongaigaon','assam gsdp'],
    'Environment':     ['kaziranga','manas','orang','nameri','dibru-saikhowa','hoolock gibbon',
                        'golden langur','pygmy hog','greater adjutant','deepor beel'],
}

def classify_apsc_subject(text: str) -> str:
    text_lower = text.lower()
    scores = {subj: 0 for subj in APSC_SUBJECT_KEYWORDS}
    for subj, keywords in APSC_SUBJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[subj] += 1
    best = max(scores, key=scores.get)
    # fallback to general classification
    if scores[best] == 0:
        gen_subj = classify_subject(text)
        mapping = {'History': 'History', 'Geography': 'Geography', 'Polity': 'Polity',
                   'Economy': 'Economy', 'Environment': 'Environment', 'Science & Tech': 'Science'}
        return mapping.get(gen_subj, 'History')
    return best


def parse_apsc_page(soup: BeautifulSoup, source_name: str, offset: int = 0) -> list[dict]:
    """Parse APSC question page (handles GKToday and IndiaBix structures)."""
    questions = []

    # Try IndiaBix structure first
    containers = soup.find_all('div', class_='bix-div-container')
    if containers:
        from indiabix_scraper import parse_questions as parse_ib
        ib_qs = parse_ib(soup, 'Assam History', 'apsc-ib')  # dummy subject, we reclassify
        for q in ib_qs:
            q['subject'] = classify_apsc_subject(q['text'])
            q['source'] = source_name
        return ib_qs

    # Try GKToday structure
    q_boxes = soup.find_all('div', class_=re.compile(r'quiz|question', re.I))
    if q_boxes:
        for i, box in enumerate(q_boxes):
            try:
                q_text = box.get_text(separator=' ', strip=True)[:500]
                if len(q_text) < 15:
                    continue
                questions.append({
                    'id': f"{source_name}-{offset+i}",
                    'subject': classify_apsc_subject(q_text),
                    'difficulty': 'medium',
                    'text': q_text,
                    'options': ['', '', '', ''],
                    'correct': 0,
                    'explanation': '',
                    'source': source_name,
                })
            except Exception:
                continue

    return questions


def scrape_apsc_pyqs() -> list[dict]:
    """Scrape APSC-relevant questions from GKToday and IndiaBix."""
    all_questions = []
    output_file = RAW_DIR / "pyq_apsc_raw.json"

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        logger.info(f"Loaded {len(all_questions)} existing APSC PYQs")

    existing_ids = {q['id'] for q in all_questions}

    for i, url in enumerate(APSC_SOURCES):
        logger.info(f"\nFetching APSC source: {url}")
        soup = fetch(url)
        if not soup:
            time.sleep(2)
            continue

        source_name = f"apsc-src{i}"
        qs = parse_apsc_page(soup, source_name, offset=len(all_questions))
        new_qs = [q for q in qs if q['id'] not in existing_ids and
                  len(q.get('options', [])) == 4 and all(q['options'])]
        all_questions.extend(new_qs)
        existing_ids.update(q['id'] for q in new_qs)
        logger.info(f"  +{len(new_qs)} questions (total: {len(all_questions)})")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=2)

        time.sleep(random.uniform(2, 4))

    logger.info(f"\nAPSC PYQs total: {len(all_questions)}")
    return all_questions


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PYQ Scraper for ExamForge')
    parser.add_argument(
        '--exam', choices=['upsc', 'cat', 'apsc', 'all'],
        default='all',
    )
    args = parser.parse_args()

    if args.exam in ('upsc', 'all'):
        scrape_upsc_pyqs()
    if args.exam in ('cat', 'all'):
        scrape_cat_pyqs()
    if args.exam in ('apsc', 'all'):
        scrape_apsc_pyqs()
