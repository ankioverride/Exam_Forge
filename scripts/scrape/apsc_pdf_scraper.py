#!/usr/bin/env python3
"""
APSC PDF Scraper
-----------------
Downloads APSC Prelims question paper PDFs from assamcareer.com (Google Drive links)
and extracts MCQs using pdfplumber + regex.

Requires: pip install pdfplumber gdown requests beautifulsoup4

Usage:
    python apsc_pdf_scraper.py
    python apsc_pdf_scraper.py --limit 10   # only first N PDFs
"""

import re
import json
import time
import logging
import argparse
import tempfile
from pathlib import Path

import requests
import pdfplumber
import gdown
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)
PDF_DIR = RAW_DIR / "pdfs"
PDF_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = RAW_DIR / "apsc_pdf_raw.json"

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# assamcareer.com pages with APSC question paper PDFs
SOURCE_PAGES = [
    'https://www.assamcareer.com/2020/08/apsc-question-paper.html',
]

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3,
              'a': 0, 'b': 1, 'c': 2, 'd': 3}

APSC_SUBJECT_KEYWORDS = {
    'Assam History':   ['ahom','lachit','saraighat','yandabo','sukaphaa','borphukan',
                        'maniram','moamoriya','burmese','koch','kachari','assam accord',
                        'phulaguri','ahom kingdom','assam history','kamarupa'],
    'Assam Geography': ['brahmaputra','barak','kaziranga','manas','majuli','kopili',
                        'subansiri','lohit','dibrugarh','tinsukia','kamrup','nagaon',
                        'karbi anglong','golaghat','jorhat','sibsagar','guwahati'],
    'Art & Culture':   ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi',
                        'ankiya','bhaona','ojapali','kamakhya','satra','rongali',
                        'kongali','bhogali','dhol','pepa','assam culture'],
    'Polity':          ['sixth schedule','bodoland','assam accord','nrc','article 371',
                        'assam legislative','gauhati high court','btc','constitution',
                        'parliament','president','supreme court','governor','election'],
    'Economy':         ['digboi','oil india','numaligarh','ongc','assam tea','tea board',
                        'gdp','rbi','sebi','banking','budget','gst'],
    'Environment':     ['kaziranga','manas','orang','nameri','hoolock','golden langur',
                        'pygmy hog','greater adjutant','deepor beel','wildlife','forest',
                        'national park','rhino'],
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


def get_drive_file_id(url: str) -> str | None:
    m = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    return m.group(1) if m else None


def get_pdf_links(page_url: str) -> list[str]:
    """Fetch a source page and extract Google Drive PDF links."""
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'lxml')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'drive.google.com/file/d/' in href:
                links.append(href)
        # Deduplicate
        seen = set()
        unique = []
        for l in links:
            fid = get_drive_file_id(l)
            if fid and fid not in seen:
                seen.add(fid)
                unique.append(l)
        return unique
    except Exception as e:
        logger.warning(f"Failed to fetch {page_url}: {e}")
        return []


def download_pdf(drive_url: str, dest_path: Path) -> bool:
    """Download a Google Drive file using gdown."""
    file_id = get_drive_file_id(drive_url)
    if not file_id:
        return False
    try:
        result = gdown.download(id=file_id, output=str(dest_path), quiet=True)
        if result and Path(result).exists() and Path(result).stat().st_size > 1000:
            return True
        return False
    except Exception as e:
        logger.debug(f"gdown failed for {file_id}: {e}")
        return False


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber."""
    try:
        text_parts = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return '\n'.join(text_parts)
    except Exception as e:
        logger.debug(f"PDF read error {pdf_path}: {e}")
        return ''


def parse_mcqs_from_text(text: str, source_id: str) -> list[dict]:
    """
    Parse MCQs from raw PDF text.
    Handles common APSC paper formats:
      1. Question text
         (A) opt  (B) opt  (C) opt  (D) opt
         Ans: B
    """
    questions = []
    lines = text.split('\n')

    # Join lines into paragraphs for easier parsing
    full_text = '\n'.join(lines)
    # Normalize common encoding issues
    full_text = re.sub(r'\s+', ' ', full_text)

    # Pattern 1: numbered questions with (A)/(B)/(C)/(D) options
    # Matches: "1. question text (A) opt (B) opt (C) opt (D) opt"
    # Followed optionally by "Answer: X" or "Ans: X"

    q_pattern = re.compile(
        r'(?:^|\n)\s*(\d{1,3})[.)]\s+'         # question number
        r'(.+?)'                                  # question text
        r'\(?[Aa]\)?\s*(.+?)'                    # option A
        r'\(?[Bb]\)?\s*(.+?)'                    # option B
        r'\(?[Cc]\)?\s*(.+?)'                    # option C
        r'\(?[Dd]\)?\s*(.+?)'                    # option D
        r'(?:\s*[Aa]ns(?:wer)?[.:\s]+\(?([ABCDabcd])\)?)?'  # optional answer
        r'(?=\n\s*\d{1,3}[.)]|\Z)',              # lookahead: next question or end
        re.DOTALL
    )

    for mi, m in enumerate(q_pattern.finditer(full_text)):
        q_num = m.group(1)
        q_text = re.sub(r'\s+', ' ', m.group(2)).strip().rstrip('?')
        opts = [re.sub(r'\s+', ' ', m.group(i)).strip() for i in range(3, 7)]
        ans_letter = m.group(7)

        if len(q_text) < 10:
            continue
        if any(len(o) < 1 for o in opts):
            continue
        if not ans_letter:
            continue

        correct_idx = ANSWER_MAP.get(ans_letter.upper())
        if correct_idx is None:
            continue

        questions.append({
            'id':          f"pdf-{source_id}-{q_num}",
            'subject':     classify_subject(q_text),
            'difficulty':  'medium',
            'text':        q_text,
            'options':     opts,
            'correct':     correct_idx,
            'explanation': '',
            'source':      f'pdf-{source_id}',
        })

    # Pattern 2: block format — question on one line, options on next lines
    # "1. Question?\n(a) A\n(b) B\n(c) C\n(d) D\nAnswer: C"
    if not questions:
        block_pattern = re.compile(
            r'(\d{1,3})[.)]\s+(.{10,200}?)\n'
            r'\(?[Aa]\)?\s*(.+?)\n'
            r'\(?[Bb]\)?\s*(.+?)\n'
            r'\(?[Cc]\)?\s*(.+?)\n'
            r'\(?[Dd]\)?\s*(.+?)\n'
            r'(?:[Aa]ns(?:wer)?[.:\s]+\(?([ABCDabcd])\)?)?',
            re.DOTALL
        )
        for mi, m in enumerate(block_pattern.finditer(full_text)):
            q_num = m.group(1)
            q_text = m.group(2).strip()
            opts = [m.group(i).strip() for i in range(3, 7)]
            ans_letter = m.group(7)
            if not ans_letter or len(q_text) < 10:
                continue
            correct_idx = ANSWER_MAP.get(ans_letter.upper())
            if correct_idx is None:
                continue
            questions.append({
                'id':          f"pdf-{source_id}-{q_num}",
                'subject':     classify_subject(q_text),
                'difficulty':  'medium',
                'text':        q_text,
                'options':     opts,
                'correct':     correct_idx,
                'explanation': '',
                'source':      f'pdf-{source_id}',
            })

    return questions


def main(limit: int = 0):
    # Load existing output
    existing = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    existing_ids = {q['id'] for q in existing}
    all_questions = list(existing)

    # Collect PDF links
    all_links = []
    for page_url in SOURCE_PAGES:
        links = get_pdf_links(page_url)
        logger.info(f"{page_url}: {len(links)} PDFs found")
        all_links.extend(links)

    if limit:
        all_links = all_links[:limit]

    logger.info(f"Total PDFs to process: {len(all_links)}")

    for i, drive_url in enumerate(all_links):
        file_id = get_drive_file_id(drive_url)
        if not file_id:
            continue

        pdf_path = PDF_DIR / f"apsc_{file_id}.pdf"
        source_id = f"apsc{i+1}"

        # Skip if already parsed
        if any(q['id'].startswith(f"pdf-{source_id}-") for q in all_questions):
            logger.info(f"[{i+1}/{len(all_links)}] {file_id}: already processed, skipping")
            continue

        logger.info(f"[{i+1}/{len(all_links)}] Downloading {file_id} ...")

        # Download if not cached
        if not pdf_path.exists():
            ok = download_pdf(drive_url, pdf_path)
            if not ok:
                logger.warning(f"  Download failed for {file_id}")
                continue
            time.sleep(2)  # polite delay

        # Extract and parse
        logger.info(f"  Extracting text from {pdf_path.name} ...")
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"  No text extracted (probably scanned image PDF)")
            continue

        qs = parse_mcqs_from_text(text, source_id)
        new_qs = [q for q in qs if q['id'] not in existing_ids]
        all_questions.extend(new_qs)
        for q in new_qs:
            existing_ids.add(q['id'])

        logger.info(f"  {len(new_qs)} questions extracted | total: {len(all_questions)}")

        # Save after each PDF
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=2)

    logger.info(f"\nDone. {len(all_questions)} total → {OUTPUT_FILE}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Max PDFs to process (0 = all)')
    args = parser.parse_args()
    main(args.limit)
