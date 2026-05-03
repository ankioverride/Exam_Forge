#!/usr/bin/env python3
"""
APSC Web Scraper
-----------------
Scrapes Assam GK / APSC questions from multiple static web sources:
  - GKSeries.com  — APSC PYQ solved questions
  - GKUnboxing    — Assam GK MCQ (via Blogger JSON feed)
  - GKToday       — Assam GK quiz pages
  - EducationForAssam — 1000 Assam GK quiz posts

Output: raw/apsc_web_raw.json
Run pipeline.py --exam apsc afterwards to merge.

Usage:
    python apsc_web_scraper.py
    python apsc_web_scraper.py --source gkseries
    python apsc_web_scraper.py --source gkunboxing
    python apsc_web_scraper.py --source gktoday
    python apsc_web_scraper.py --source efa
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import random
import argparse
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scrape_apsc_web.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = RAW_DIR / "apsc_web_raw.json"

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

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

APSC_SUBJECT_KEYWORDS = {
    'Assam History':   ['ahom','assam history','lachit','saraighat','mughal','yandabo',
                        'sukaphaa','borphukan','maniram','moamoriya','burmese','koch',
                        'kachari','chutia','assam accord','phulaguri','ahom kingdom'],
    'Assam Geography': ['brahmaputra','barak','kaziranga','manas','majuli','kopili',
                        'subansiri','lohit','dibrugarh','tinsukia','kamrup','nagaon',
                        'karbi anglong','golaghat','jorhat','sibsagar','guwahati','assam district',
                        'digboi','numaligarh','assam flood','char island'],
    'Art & Culture':   ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi',
                        'ankiya','bhaona','ojapali','kamakhya','vaishnavite','satra',
                        'rongali','kongali','bhogali','dhol','pepa','zikir','zari',
                        'assamese literature','hemkosh','jonaki','madhavdeva'],
    'Polity':          ['sixth schedule','bodoland','assam accord','nrc','imdt','article 371',
                        'assam legislative','gauhati high court','btc','karbi council',
                        'assam assembly','assam cm','dispur','governor assam'],
    'Economy':         ['digboi','oil india','numaligarh','ongc','tea assam','assam tea',
                        'brahmaputra cracker','bhel','assam gsdp','assam industry',
                        'assam agriculture','assam budget'],
    'Environment':     ['kaziranga','manas','orang','nameri','dibru-saikhowa','hoolock',
                        'golden langur','pygmy hog','greater adjutant','deepor beel',
                        'assam wildlife','assam forest'],
    'History':         ['india history','mughal','british','colonial','revolt','gandhi',
                        'nehru','congress','maurya','medieval','ancient','independence'],
    'Geography':       ['india geography','river','mountain','climate','monsoon',
                        'tropic','india map','state capital'],
    'Polity':          ['constitution','article','parliament','president','supreme court',
                        'fundamental rights','election','panchayat','emergency'],
    'Economy':         ['gdp','rbi','sebi','banking','inflation','five year plan',
                        'mgnrega','gst','budget'],
    'Science':         ['atom','space','isro','disease','vaccine','dna','energy',
                        'computer','internet','technology','physics','chemistry','biology'],
}

def classify_apsc_subject(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for subj, keywords in APSC_SUBJECT_KEYWORDS.items():
        scores[subj] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'History'

def fetch(url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'lxml')
            elif resp.status_code in (403, 404):
                logger.warning(f"HTTP {resp.status_code}: {url}")
                return None
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
        time.sleep(2 * attempt)
    return None

def save(questions: list[dict]) -> None:
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

def load_existing() -> list[dict]:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


# ═══════════════════════════════════════════════════════════
# SOURCE 1: GKSeries.com — APSC PYQ Solved Questions
# ═══════════════════════════════════════════════════════════

GKSERIES_URLS = [
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-2",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-3",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-4",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-5",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-6",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-7",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-8",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-9",
    "https://www.gkseries.com/public-service-commission/apsc/previous-years-solved-questions-of-apsc/page-10",
]

# Also try other APSC-related GKSeries pages
GKSERIES_EXTRA_URLS = [
    "https://www.gkseries.com/assam-general-knowledge/assam-history",
    "https://www.gkseries.com/assam-general-knowledge/assam-geography",
    "https://www.gkseries.com/assam-general-knowledge/assam-polity",
    "https://www.gkseries.com/assam-general-knowledge/assam-economy",
    "https://www.gkseries.com/assam-general-knowledge/assam-culture",
    "https://www.gkseries.com/assam-general-knowledge/assam-current-affairs",
]


def parse_gkseries_page(soup: BeautifulSoup, page_id: str) -> list[dict]:
    """
    GKSeries structure:
      .mcq > .question-content  (question text)
      .options > .col-md-12.option  (A/B/C/D options)
      .collapse-{first/second/...} > .blockquote  (answer: "Answer: Option [C]")
    """
    questions = []
    mcq_blocks = soup.find_all('div', class_='mcq')

    ordinals = ['first','second','third','fourth','fifth','sixth','seventh','eighth','ninth','tenth']

    for i, block in enumerate(mcq_blocks):
        try:
            # Question text
            q_div = block.find('div', class_='question-content')
            if not q_div:
                continue
            # Remove the badge number span
            for span in q_div.find_all('span', class_='badge'):
                span.decompose()
            q_text = q_div.get_text(separator=' ', strip=True)
            if len(q_text) < 8:
                continue

            # Options
            opts_div = block.find('div', class_='options')
            if not opts_div:
                continue
            opt_divs = opts_div.find_all('div', class_='option')
            options = []
            for od in opt_divs[:4]:
                # Remove letter badge
                for span in od.find_all('span', class_='badge'):
                    span.decompose()
                opt_text = od.get_text(separator=' ', strip=True)
                options.append(opt_text)

            if len(options) < 4 or any(not o for o in options):
                continue

            # Answer — look for collapse div with ordinal id or numbered id
            correct_idx = None

            # Try ordinal id: id="first", id="second", ...
            if i < len(ordinals):
                ans_div = block.find('div', id=ordinals[i])
                if not ans_div:
                    # Try direct id on collapse
                    ans_div = block.find('div', class_=f'collapse-{ordinals[i]}')

            if ans_div:
                bq = ans_div.find('blockquote')
                if bq:
                    ans_text = bq.get_text(strip=True)
                    m = re.search(r'Option\s*\[([ABCD])\]', ans_text, re.I)
                    if m:
                        correct_idx = ANSWER_MAP.get(m.group(1).upper())

            # Fallback: search anywhere in block for "Answer: Option [X]"
            if correct_idx is None:
                full_text = block.get_text()
                m = re.search(r'Answer[:\s]+Option\s*\[([ABCD])\]', full_text, re.I)
                if m:
                    correct_idx = ANSWER_MAP.get(m.group(1).upper())

            if correct_idx is None:
                continue

            questions.append({
                'id':          f"gks-apsc-{page_id}-{i+1}",
                'subject':     classify_apsc_subject(q_text),
                'difficulty':  'medium',
                'text':        q_text,
                'options':     options,
                'correct':     correct_idx,
                'explanation': '',
                'source':      'gkseries-apsc',
            })
        except Exception as e:
            logger.debug(f"Skip: {e}")

    return questions


def scrape_gkseries(all_questions: list[dict], existing_ids: set) -> list[dict]:
    urls = GKSERIES_URLS + GKSERIES_EXTRA_URLS
    for url in urls:
        logger.info(f"GKSeries: {url}")
        soup = fetch(url)
        if not soup:
            time.sleep(2)
            continue

        # Discover all pagination pages
        page_id = url.split('/')[-1] or 'p1'
        qs = parse_gkseries_page(soup, page_id)

        # Also try to find more pages via pagination
        pagination = soup.find('ul', class_='pagination')
        if pagination:
            for a in pagination.find_all('a', href=True):
                href = a['href']
                if href and href not in [url] and 'gkseries.com' in (href if href.startswith('http') else ''):
                    pass  # handled by explicit URL list above

        new_qs = [q for q in qs if q['id'] not in existing_ids]
        all_questions.extend(new_qs)
        existing_ids.update(q['id'] for q in new_qs)
        logger.info(f"  +{len(new_qs)} (total: {len(all_questions)})")
        save(all_questions)
        time.sleep(random.uniform(1.5, 3.0))

    return all_questions


# ═══════════════════════════════════════════════════════════
# SOURCE 2: GKUnboxing — Assam GK via Blogger JSON feed
# ═══════════════════════════════════════════════════════════

GKUNBOXING_FEED = (
    "https://www.gkunboxing.com/feeds/posts/default/-/assam-gk-mcq-questions-and-answers"
    "?alt=json&max-results=500"
)

def scrape_gkunboxing(all_questions: list[dict], existing_ids: set) -> list[dict]:
    """Fetch Blogger JSON feed and parse MCQ posts."""
    logger.info("GKUnboxing: fetching Blogger JSON feed...")
    try:
        resp = session.get(GKUNBOXING_FEED, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"GKUnboxing feed: HTTP {resp.status_code}")
            return all_questions
        data = resp.json()
    except Exception as e:
        logger.warning(f"GKUnboxing feed error: {e}")
        return all_questions

    entries = data.get('feed', {}).get('entry', [])
    logger.info(f"  Found {len(entries)} posts in feed")

    for i, entry in enumerate(entries):
        try:
            # Post content is in entry.content.$t (HTML string)
            content_html = entry.get('content', {}).get('$t', '') or \
                           entry.get('summary', {}).get('$t', '')
            if not content_html:
                continue

            post_soup = BeautifulSoup(content_html, 'lxml')
            post_text = post_soup.get_text(separator='\n')

            # Parse MCQ questions from text — typical format:
            # 1. Question text?
            # A) Option A  B) Option B  C) Option C  D) Option D
            # Answer: C
            q_pattern = re.compile(
                r'(\d+)[\.:\)]\s+(.+?)\n'
                r'[Aa][\.:\)]\s*(.+?)\s*[Bb][\.:\)]\s*(.+?)\s*[Cc][\.:\)]\s*(.+?)\s*[Dd][\.:\)]\s*(.+?)(?:\n|$)',
                re.DOTALL
            )
            ans_pattern = re.compile(r'[Aa]nswer\s*[:\-]?\s*[\(\[]?\s*([ABCD])\s*[\)\]]?', re.I)

            post_qs = []
            for m in q_pattern.finditer(post_text):
                q_num = m.group(1)
                q_text = m.group(2).strip()
                opts = [m.group(j).strip() for j in range(3, 7)]

                # Find answer near this question
                start = m.start()
                nearby = post_text[start:start + 500]
                ans_m = ans_pattern.search(nearby)
                correct_idx = ANSWER_MAP.get(ans_m.group(1).upper()) if ans_m else None

                if len(q_text) < 8 or not all(opts) or correct_idx is None:
                    continue

                uid = f"gku-{i+1}-{q_num}"
                if uid in existing_ids:
                    continue

                post_qs.append({
                    'id':          uid,
                    'subject':     classify_apsc_subject(q_text),
                    'difficulty':  'easy',
                    'text':        q_text,
                    'options':     opts,
                    'correct':     correct_idx,
                    'explanation': '',
                    'source':      'gkunboxing',
                })

            new_qs = [q for q in post_qs if q['id'] not in existing_ids]
            all_questions.extend(new_qs)
            existing_ids.update(q['id'] for q in new_qs)

            if new_qs:
                logger.info(f"  Post {i+1}: +{len(new_qs)} questions (total: {len(all_questions)})")

            if i % 50 == 0:
                save(all_questions)

        except Exception as e:
            logger.debug(f"GKUnboxing post {i}: {e}")

    save(all_questions)
    logger.info(f"GKUnboxing done. Total: {len(all_questions)}")
    return all_questions


# ═══════════════════════════════════════════════════════════
# SOURCE 3: GKToday — Assam-specific quiz pages
# ═══════════════════════════════════════════════════════════

GKTODAY_ASSAM_URLS = [
    "https://www.gktoday.in/quizbase/assam-gk-questions-for-assam-public-service-commission-exams/",
    "https://www.gktoday.in/quizbase/assam-history-gk-quiz/",
    "https://www.gktoday.in/quizbase/assam-geography-quiz/",
    "https://www.gktoday.in/quizbase/assam-polity-gk-quiz/",
    "https://www.gktoday.in/quizbase/assam-economy-gk-quiz/",
    "https://www.gktoday.in/quizbase/assam-culture-gk-quiz/",
    "https://www.gktoday.in/quizbase/assam-environment-gk-quiz/",
    "https://www.gktoday.in/quizbase/north-east-india-gk-quiz/",
    "https://www.gktoday.in/quizbase/assam-current-affairs-quiz/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2023-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2022-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2021-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2020-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2019-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2018-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2017-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2016-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2015-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2014-general-studies/",
    "https://www.gktoday.in/quizbase/apsc-cce-prelims-2013-general-studies/",
]

def parse_gktoday_static(soup: BeautifulSoup, source_name: str) -> list[dict]:
    """
    GKToday quiz structure (static part):
      .quiz-question-box > .quiz-question  (question text)
      .quiz-option  (options, 4 of them)
      GKToday uses AJAX for answers — try to find hidden answer data or fallback
    """
    questions = []

    # Try multiple possible containers
    boxes = (soup.find_all('div', class_='quiz-question-box') or
             soup.find_all('div', class_=re.compile(r'quiz.?question', re.I)) or
             soup.find_all('li', class_=re.compile(r'question', re.I)))

    for i, box in enumerate(boxes):
        try:
            # Question text
            q_el = box.find(class_=re.compile(r'quiz.?question|question.?text', re.I))
            q_text = (q_el or box).get_text(separator=' ', strip=True)
            q_text = re.sub(r'^Q?\s*\d+[\.:\)]\s*', '', q_text).strip()
            if len(q_text) < 10:
                continue

            # Options
            opt_els = box.find_all(class_=re.compile(r'quiz.?option|option.?text', re.I))
            options = [re.sub(r'^[ABCD][\.:\)]\s*', '', el.get_text(strip=True))
                       for el in opt_els[:4]]
            if len(options) < 4:
                continue

            # GKToday answers are AJAX-loaded, but sometimes stored in data attributes
            # Try data-answer, data-correct, or hidden inputs
            ans_el = box.find(attrs={'data-answer': True}) or \
                     box.find(attrs={'data-correct': True}) or \
                     box.find('input', {'type': 'hidden'})

            correct_idx = None
            if ans_el:
                val = (ans_el.get('data-answer') or ans_el.get('data-correct') or
                       ans_el.get('value', '')).strip().upper()
                correct_idx = ANSWER_MAP.get(val)

            # If we can't get the answer, skip (don't add wrong data)
            if correct_idx is None:
                continue

            questions.append({
                'id':          f"gkt-{source_name}-{i+1}",
                'subject':     classify_apsc_subject(q_text),
                'difficulty':  'medium',
                'text':        q_text,
                'options':     options,
                'correct':     correct_idx,
                'explanation': '',
                'source':      f'gktoday-{source_name}',
            })
        except Exception as e:
            logger.debug(f"GKToday skip: {e}")

    return questions


def scrape_gktoday_assam(all_questions: list[dict], existing_ids: set) -> list[dict]:
    for url in GKTODAY_ASSAM_URLS:
        logger.info(f"GKToday: {url}")
        soup = fetch(url)
        if not soup:
            time.sleep(2)
            continue

        slug = url.rstrip('/').split('/')[-1][:20]
        qs = parse_gktoday_static(soup, slug)
        new_qs = [q for q in qs if q['id'] not in existing_ids]
        all_questions.extend(new_qs)
        existing_ids.update(q['id'] for q in new_qs)

        if new_qs:
            logger.info(f"  +{len(new_qs)} (total: {len(all_questions)})")
        save(all_questions)
        time.sleep(random.uniform(1.5, 3.0))

    return all_questions


# ═══════════════════════════════════════════════════════════
# SOURCE 4: EducationForAssam blog posts — Assam GK quizzes
# ═══════════════════════════════════════════════════════════

EFA_SITEMAP_URL = "https://www.educationforassam.com/sitemap.xml"
EFA_BASE = "https://www.educationforassam.com"

def parse_efa_post(soup: BeautifulSoup, post_url: str) -> list[dict]:
    """Parse an EducationForAssam blog post for MCQ questions."""
    questions = []
    text = soup.get_text(separator='\n')

    # Common blog MCQ format:
    # Q1. Question text?
    # (a) Option A  (b) Option B  (c) Option C  (d) Option D
    # Ans: (a) / Answer: a / উত্তৰ: a

    patterns = [
        # English numbered
        re.compile(
            r'(?:Q\.?\s*)?(\d+)[\.:\)]\s+(.+?)\n'
            r'[\(\[]?[Aa][\)\]]\s*(.+?)\s*[\(\[]?[Bb][\)\]]\s*(.+?)\s*[\(\[]?[Cc][\)\]]\s*(.+?)\s*[\(\[]?[Dd][\)\]]\s*(.+?)(?=\n|$)',
            re.DOTALL
        ),
    ]
    ans_patterns = [
        re.compile(r'[Aa]ns(?:wer)?[:\s]+[\(\[]?\s*([ABCDabcd])\s*[\)\]]?'),
        re.compile(r'উত্তৰ[:\s]+[\(\[]?\s*([ABCDabcd])\s*[\)\]]?'),
        re.compile(r'Correct[:\s]+[\(\[]?\s*([ABCDabcd])\s*[\)\]]?'),
    ]

    for pattern in patterns:
        for m in pattern.finditer(text):
            try:
                q_num = m.group(1)
                q_text = m.group(2).strip()
                opts = [m.group(j).strip() for j in range(3, 7)]

                nearby = text[m.start():m.start() + 600]
                correct_idx = None
                for ap in ans_patterns:
                    ans_m = ap.search(nearby)
                    if ans_m:
                        correct_idx = ANSWER_MAP.get(ans_m.group(1).upper())
                        break

                if len(q_text) < 8 or not all(opts) or correct_idx is None:
                    continue

                slug = post_url.rstrip('/').split('/')[-1][:15]
                questions.append({
                    'id':          f"efa-{slug}-{q_num}",
                    'subject':     classify_apsc_subject(q_text),
                    'difficulty':  'easy',
                    'text':        q_text,
                    'options':     opts,
                    'correct':     correct_idx,
                    'explanation': '',
                    'source':      'educationforassam',
                })
            except Exception:
                continue

    return questions


EFA_QUIZ_URLS = [
    "https://www.educationforassam.com/2021/08/1000-assamese-general-knowledge-quiz.html",
    "https://www.educationforassam.com/2021/08/assam-history-gk-quiz.html",
    "https://www.educationforassam.com/2021/08/assam-geography-quiz.html",
    "https://www.educationforassam.com/2021/08/assam-polity-quiz.html",
    "https://www.educationforassam.com/2021/09/assam-culture-quiz.html",
    "https://www.educationforassam.com/search/label/APSC",
    "https://www.educationforassam.com/search/label/Assam%20GK",
    "https://www.educationforassam.com/search/label/MCQ",
]

def scrape_efa(all_questions: list[dict], existing_ids: set) -> list[dict]:
    post_urls = set(EFA_QUIZ_URLS)

    for start_url in list(EFA_QUIZ_URLS):
        soup = fetch(start_url)
        if not soup:
            continue
        # Collect post links from label/search pages
        for a in soup.find_all('a', href=True):
            href = a['href']
            if EFA_BASE in href and '/20' in href and '.html' in href:
                post_urls.add(href)
        time.sleep(random.uniform(1.0, 2.0))

    logger.info(f"EducationForAssam: {len(post_urls)} post URLs to scrape")

    for url in sorted(post_urls):
        logger.info(f"  EFA: {url}")
        soup = fetch(url)
        if not soup:
            time.sleep(2)
            continue

        qs = parse_efa_post(soup, url)
        new_qs = [q for q in qs if q['id'] not in existing_ids]
        all_questions.extend(new_qs)
        existing_ids.update(q['id'] for q in new_qs)

        if new_qs:
            logger.info(f"    +{len(new_qs)} (total: {len(all_questions)})")
        save(all_questions)
        time.sleep(random.uniform(1.5, 3.0))

    return all_questions


# ═══════════════════════════════════════════════════════════
# SOURCE 5: Gradient IAS — APSC CCE Subject-wise MCQs
# ═══════════════════════════════════════════════════════════

GRADIENT_URLS = [
    "https://www.gradientias.com/aspcassam",
    "https://www.gradientias.com/apsc-assam-history",
    "https://www.gradientias.com/apsc-assam-geography",
    "https://www.gradientias.com/apsc-assam-culture",
    "https://www.gradientias.com/apsc-assam-polity",
    "https://www.gradientias.com/apsc-general-science",
    "https://www.gradientias.com/apsc-economy",
]

def parse_gradient_page(soup: BeautifulSoup, source: str) -> list[dict]:
    questions = []
    # Try common MCQ containers
    for container_class in ['mcq', 'question-block', 'quiz-question', 'question']:
        blocks = soup.find_all('div', class_=container_class)
        if blocks:
            break

    if not blocks:
        # Parse text
        text = soup.get_text(separator='\n')
        return _parse_text_mcq(text, source)

    for i, block in enumerate(blocks):
        try:
            q_text = block.find(class_=re.compile(r'question', re.I))
            q_text = (q_text or block).get_text(separator=' ', strip=True)
            q_text = re.sub(r'^Q?\s*\d+[\.:\)]\s*', '', q_text).strip()

            opts_els = block.find_all(class_=re.compile(r'option|choice', re.I))
            options = [re.sub(r'^[ABCD][\.:\)]\s*', '', el.get_text(strip=True))
                       for el in opts_els[:4]]
            if len(options) < 4:
                continue

            ans_el = (block.find(class_=re.compile(r'answer|correct', re.I)) or
                      block.find(attrs={'data-answer': True}))
            correct_idx = None
            if ans_el:
                txt = (ans_el.get('data-answer') or ans_el.get_text(strip=True)).upper()
                m = re.search(r'[ABCD]', txt)
                if m:
                    correct_idx = ANSWER_MAP.get(m.group())

            if correct_idx is None:
                continue

            questions.append({
                'id':          f"grad-{source}-{i+1}",
                'subject':     classify_apsc_subject(q_text),
                'difficulty':  'medium',
                'text':        q_text,
                'options':     options,
                'correct':     correct_idx,
                'explanation': '',
                'source':      f'gradient-{source}',
            })
        except Exception:
            continue
    return questions

def _parse_text_mcq(text: str, source: str) -> list[dict]:
    """Generic text-based MCQ parser."""
    questions = []
    pattern = re.compile(
        r'(\d+)[\.:\)]\s+(.+?)\n'
        r'[\(\[]?[Aa][\)\]\.]\s*(.+?)\s*[\(\[]?[Bb][\)\]\.]\s*(.+?)\s*'
        r'[\(\[]?[Cc][\)\]\.]\s*(.+?)\s*[\(\[]?[Dd][\)\]\.]\s*(.+?)(?=\n\d+[\.:\)]|\Z)',
        re.DOTALL
    )
    ans_p = re.compile(r'[Aa]ns(?:wer)?[:\s]+[\(\[]?\s*([ABCD])\s*[\)\]]?', re.I)

    for m in pattern.finditer(text):
        try:
            q_text = m.group(2).strip()
            opts = [m.group(j).strip() for j in range(3, 7)]
            nearby = text[m.start():m.start()+400]
            am = ans_p.search(nearby)
            if not am or len(q_text) < 8 or not all(opts):
                continue
            questions.append({
                'id': f"txt-{source}-{m.group(1)}",
                'subject': classify_apsc_subject(q_text),
                'difficulty': 'medium',
                'text': q_text,
                'options': opts,
                'correct': ANSWER_MAP.get(am.group(1).upper(), 0),
                'explanation': '',
                'source': source,
            })
        except Exception:
            continue
    return questions


def scrape_gradient(all_questions: list[dict], existing_ids: set) -> list[dict]:
    for url in GRADIENT_URLS:
        logger.info(f"Gradient IAS: {url}")
        soup = fetch(url)
        if not soup:
            time.sleep(2)
            continue
        slug = url.rstrip('/').split('/')[-1][:15]
        qs = parse_gradient_page(soup, slug)
        new_qs = [q for q in qs if q['id'] not in existing_ids]
        all_questions.extend(new_qs)
        existing_ids.update(q['id'] for q in new_qs)
        if new_qs:
            logger.info(f"  +{len(new_qs)} (total: {len(all_questions)})")
        save(all_questions)
        time.sleep(random.uniform(2, 4))
    return all_questions


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

SOURCES = {
    'gkseries':   scrape_gkseries,
    'gkunboxing': scrape_gkunboxing,
    'gktoday':    scrape_gktoday_assam,
    'efa':        scrape_efa,
    'gradient':   scrape_gradient,
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='APSC Multi-Source Web Scraper')
    parser.add_argument('--source', choices=list(SOURCES.keys()) + ['all'], default='all')
    args = parser.parse_args()

    all_questions = load_existing()
    existing_ids = {q['id'] for q in all_questions}
    logger.info(f"Starting with {len(all_questions)} existing questions")

    sources_to_run = list(SOURCES.items()) if args.source == 'all' else [(args.source, SOURCES[args.source])]

    for name, fn in sources_to_run:
        logger.info(f"\n{'='*50}\nSCRAPING: {name.upper()}\n{'='*50}")
        all_questions = fn(all_questions, existing_ids)

    logger.info(f"\nDone! {len(all_questions)} total questions saved to {OUTPUT_FILE}")
