#!/usr/bin/env python3
"""
GKToday Assam GK Scraper
-------------------------
Scrapes https://www.gktoday.in/quizbase/assam-gk-questions-for-assam-public-service-commission-exams
Static HTML — questions, options, correct answer, and notes all in the page source.

Output: raw/gktoday_apsc_raw.json
"""

import re
import json
import time
import logging
import requests
from pathlib import Path
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = RAW_DIR / "gktoday_apsc_raw.json"

BASE_URL = "https://www.gktoday.in/quizbase/assam-gk-questions-for-assam-public-service-commission-exams"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

APSC_SUBJECT_KEYWORDS = {
    'Assam History':   ['ahom','lachit','saraighat','yandabo','sukaphaa','borphukan',
                        'maniram','moamoriya','burmese','koch','kachari','assam accord',
                        'phulaguri','ahom kingdom','assam history','battle of saraighat',
                        'kamarupa','chilarai','bura gohain','baro bhuiyans'],
    'Assam Geography': ['brahmaputra','barak','kaziranga','manas','majuli','kopili',
                        'subansiri','lohit','dibrugarh','tinsukia','kamrup','nagaon',
                        'karbi anglong','golaghat','jorhat','sibsagar','guwahati',
                        'assam district','assam river','assam geography','dhubri',
                        'hailakandi','cachar','darrang','sonitpur'],
    'Art & Culture':   ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi',
                        'ankiya','bhaona','ojapali','kamakhya','satra','rongali',
                        'kongali','bhogali','dhol','pepa','assam culture','assam dance',
                        'xatra','vaishnavism','madhabdev','name ghar'],
    'Polity':          ['sixth schedule','bodoland','assam accord','nrc','article 371',
                        'assam legislative','gauhati high court','btc','constitution',
                        'parliament','president','supreme court','governor','election',
                        'aagp','agp','autonomous council','bodo'],
    'Economy':         ['digboi','oil india','numaligarh','ongc','assam tea','tea board',
                        'assam gsdp','gdp','rbi','sebi','banking','budget','gst',
                        'assam silk','handicraft','handloom'],
    'Environment':     ['kaziranga','manas','orang','nameri','hoolock','golden langur',
                        'pygmy hog','greater adjutant','deepor beel','wildlife','forest',
                        'national park','assam wildlife','one-horned','rhino'],
    'History':         ['mughal','british','colonial','gandhi','nehru','congress',
                        'maurya','medieval','ancient','independence','revolt','dynasty'],
    'Science':         ['isro','space','mission','chandrayaan','covid','vaccine','dna',
                        'technology','internet','artificial intelligence','nuclear'],
}


def classify_subject(text: str) -> str:
    text_lower = text.lower()
    scores = {s: sum(1 for kw in kws if kw in text_lower)
              for s, kws in APSC_SUBJECT_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'History'


def parse_page(html: str, page_num: int) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    blocks = soup.select('.sques_quiz')
    questions = []

    for idx, block in enumerate(blocks):
        # Question text
        q_elem = block.select_one('.wp_quiz_question')
        if not q_elem:
            continue
        # Remove the "1. " number span
        num_span = q_elem.select_one('.quesno')
        if num_span:
            num_span.decompose()
        q_text = q_elem.get_text(strip=True)
        if len(q_text) < 10:
            continue

        # Options: "[A] opt\n[B] opt\n[C] opt\n[D] opt"
        opts_elem = block.select_one('.wp_quiz_question_options')
        if not opts_elem:
            continue
        opts_html = opts_elem.decode_contents()
        # Split by [A], [B], [C], [D] markers
        opt_parts = re.split(r'\[([ABCD])\]', opts_html)
        # opt_parts = ['', 'A', ' text<br/>', 'B', ' text<br/>', ...]
        options = {}
        for i in range(1, len(opt_parts) - 1, 2):
            letter = opt_parts[i].strip()
            raw_text = opt_parts[i + 1]
            text = BeautifulSoup(raw_text, 'lxml').get_text(strip=True).rstrip('?.,')
            options[letter] = text

        if len(options) < 4:
            continue
        opts_list = [options.get(l, '') for l in ['A', 'B', 'C', 'D']]
        if any(len(o) < 1 for o in opts_list):
            continue

        # Correct answer: "Correct Answer: C [Kamakhya Temple]"
        ans_elem = block.select_one('.ques_answer')
        if not ans_elem:
            continue
        ans_text = ans_elem.get_text(strip=True)
        # Extract letter
        m = re.search(r'Correct Answer.*?([ABCD])\s*[\[\(]', ans_text)
        if not m:
            m = re.search(r'([ABCD])\s*[\[\(]', ans_text)
        if not m:
            continue
        correct_idx = ANSWER_MAP.get(m.group(1))
        if correct_idx is None:
            continue

        # Explanation from notes
        notes_elem = block.select_one('.answer_hint')
        explanation = ''
        if notes_elem:
            explanation = notes_elem.get_text(separator=' ', strip=True)
            explanation = re.sub(r'^Notes:\s*', '', explanation).strip()

        questions.append({
            'id':          f"gkt-{page_num}-{idx}",
            'subject':     classify_subject(q_text),
            'difficulty':  'medium',
            'text':        q_text,
            'options':     opts_list,
            'correct':     correct_idx,
            'explanation': explanation,
            'source':      'gktoday',
        })

    return questions


def get_max_page(html: str) -> int:
    soup = BeautifulSoup(html, 'lxml')
    page_links = soup.select('a[href*="pageno"]')
    nums = []
    for a in page_links:
        m = re.search(r'pageno=(\d+)', a['href'])
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 1


def scrape():
    all_questions = []

    # Page 1
    logger.info(f"Fetching page 1 ...")
    r = requests.get(BASE_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    max_page = get_max_page(r.text)
    logger.info(f"Total pages: {max_page}")
    qs = parse_page(r.text, 1)
    all_questions.extend(qs)
    logger.info(f"  Page 1: {len(qs)} questions")

    for page in range(2, max_page + 1):
        time.sleep(1.5)
        url = f"{BASE_URL}?pageno={page}"
        logger.info(f"Fetching page {page} ...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            qs = parse_page(r.text, page)
            all_questions.extend(qs)
            logger.info(f"  Page {page}: {len(qs)} questions")
        except Exception as e:
            logger.warning(f"  Page {page} failed: {e}")

    logger.info(f"\nTotal: {len(all_questions)} questions")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved → {OUTPUT_FILE}")
    return all_questions


if __name__ == '__main__':
    scrape()
