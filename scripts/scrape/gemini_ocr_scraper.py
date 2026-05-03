#!/usr/bin/env python3
"""
Gemini OCR Scraper
-------------------
Uses Gemini Vision to extract MCQs from scanned APSC question paper PDFs.
Uploads each PDF directly to the Gemini Files API, then asks it to extract
all MCQs with options and correct answers.

PDFs are pre-downloaded by apsc_pdf_scraper.py into raw/pdfs/

Requires: pip install google-genai pymupdf

Usage:
    python gemini_ocr_scraper.py
    python gemini_ocr_scraper.py --limit 5     # process first 5 PDFs only
    python gemini_ocr_scraper.py --model gemini-2.5-pro
"""

import os
import re
import json
import time
import logging
import argparse
from pathlib import Path

from google import genai
from google.genai import types

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('gemini_ocr.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
DEFAULT_MODEL  = 'gemini-2.5-pro'
FALLBACK_MODEL = 'gemini-2.5-flash'

RAW_DIR     = Path(__file__).parent / "raw"
PDF_DIR     = RAW_DIR / "pdfs"
OUTPUT_FILE = RAW_DIR / "gemini_ocr_raw.json"

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3,
              'a': 0, 'b': 1, 'c': 2, 'd': 3,
              '1': 0, '2': 1, '3': 2, '4': 3}

APSC_SUBJECT_KEYWORDS = {
    'Assam History':   ['ahom','lachit','saraighat','yandabo','sukaphaa','borphukan',
                        'maniram','moamoriya','burmese','koch','kachari','assam accord',
                        'phulaguri','ahom kingdom','kamarupa','chilarai','bura gohain'],
    'Assam Geography': ['brahmaputra','barak','kaziranga','manas','majuli','kopili',
                        'subansiri','lohit','dibrugarh','tinsukia','kamrup','nagaon',
                        'karbi anglong','golaghat','jorhat','sibsagar','guwahati',
                        'dhubri','hailakandi','cachar','darrang','sonitpur'],
    'Art & Culture':   ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi',
                        'ankiya','bhaona','ojapali','kamakhya','satra','rongali',
                        'kongali','bhogali','dhol','pepa','xatra','vaishnavism',
                        'madhabdev','name ghar','assam culture','assam dance'],
    'Polity':          ['sixth schedule','bodoland','assam accord','nrc','article 371',
                        'assam legislative','gauhati high court','btc','constitution',
                        'parliament','president','supreme court','governor','election',
                        'aagp','agp','autonomous council','bodo','legislature'],
    'Economy':         ['digboi','oil india','numaligarh','ongc','assam tea','tea board',
                        'assam gsdp','gdp','rbi','sebi','banking','budget','gst',
                        'assam silk','handicraft','handloom','ril','nalco'],
    'Environment':     ['kaziranga','manas','orang','nameri','hoolock','golden langur',
                        'pygmy hog','greater adjutant','deepor beel','wildlife','forest',
                        'national park','assam wildlife','one-horned','rhino','elephant'],
    'History':         ['mughal','british','colonial','gandhi','nehru','congress',
                        'maurya','medieval','ancient','independence','revolt','dynasty',
                        'world war','sepoy','partition'],
    'Science':         ['isro','space','mission','chandrayaan','covid','vaccine','dna',
                        'technology','internet','artificial intelligence','nuclear',
                        'satellite','physics','chemistry','biology'],
}


def classify_subject(text: str) -> str:
    t = text.lower()
    scores = {s: sum(1 for kw in kws if kw in t) for s, kws in APSC_SUBJECT_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'History'


EXTRACTION_PROMPT = """
You are extracting MCQ questions from an APSC (Assam Public Service Commission) exam paper.

Extract EVERY multiple-choice question from this document. For each question output a JSON object on a single line:
{"q": "<question text>", "a": "<option A text>", "b": "<option B text>", "c": "<option C text>", "d": "<option D text>", "ans": "<A or B or C or D>"}

Rules:
- Include ALL MCQs you find — do not skip any
- The "ans" field must be exactly one letter: A, B, C, or D
- If the answer key is at the end, match each question number to its answer
- Remove question numbers from the question text
- If an option is missing, write "N/A"
- Output ONLY the JSON lines, nothing else

Start extracting:
"""


def call_gemini_with_pdf(client, pdf_path: Path, model: str) -> str:
    """Upload PDF to Files API and extract MCQs via Gemini."""
    logger.info(f"  Uploading {pdf_path.name} to Gemini Files API ...")
    with open(pdf_path, 'rb') as f:
        uploaded = client.files.upload(
            file=f,
            config=types.UploadFileConfig(
                display_name=pdf_path.stem,
                mime_type='application/pdf',
            )
        )

    logger.info(f"  Calling {model} for extraction ...")
    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_uri(file_uri=uploaded.uri, mime_type='application/pdf'),
                EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        return response.text or ''
    finally:
        # Clean up uploaded file
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


def parse_gemini_output(raw: str, source_id: str) -> list[dict]:
    """Parse JSON lines output from Gemini into question dicts."""
    questions = []
    seen = set()

    for line in raw.split('\n'):
        line = line.strip()
        if not line.startswith('{'):
            continue
        # Clean up common Gemini JSON artifacts
        line = re.sub(r'```json?', '', line).strip('`').strip()
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Try to repair common issues
            try:
                line = re.sub(r',\s*}', '}', line)
                obj = json.loads(line)
            except Exception:
                continue

        q_text = obj.get('q', '').strip()
        if len(q_text) < 10:
            continue

        opts = [
            obj.get('a', '').strip(),
            obj.get('b', '').strip(),
            obj.get('c', '').strip(),
            obj.get('d', '').strip(),
        ]
        if any(len(o) < 1 or o == 'N/A' for o in opts):
            continue

        ans_letter = obj.get('ans', '').strip().upper()
        correct_idx = ANSWER_MAP.get(ans_letter)
        if correct_idx is None:
            continue

        # Dedup by question text
        norm = re.sub(r'\s+', ' ', q_text.lower())
        if norm in seen:
            continue
        seen.add(norm)

        questions.append({
            'id':          f"ocr-{source_id}-{len(questions)}",
            'subject':     classify_subject(q_text),
            'difficulty':  'medium',
            'text':        q_text,
            'options':     opts,
            'correct':     correct_idx,
            'explanation': '',
            'source':      f'gemini-ocr-{source_id}',
        })

    return questions


def main(limit: int = 0, model: str = DEFAULT_MODEL):
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Test connection
    logger.info(f"Using model: {model}")

    # Load existing output
    all_questions = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        logger.info(f"Loaded {len(all_questions)} existing OCR questions")

    processed_ids = {q['source'].replace('gemini-ocr-', '') for q in all_questions}

    # Find all downloaded PDFs
    pdf_files = sorted(PDF_DIR.glob('apsc_*.pdf'))
    if limit:
        pdf_files = pdf_files[:limit]

    logger.info(f"PDFs to process: {len(pdf_files)}")

    for i, pdf_path in enumerate(pdf_files):
        source_id = pdf_path.stem.replace('apsc_', '')
        if source_id in processed_ids:
            logger.info(f"[{i+1}/{len(pdf_files)}] {pdf_path.name}: already processed, skipping")
            continue

        logger.info(f"[{i+1}/{len(pdf_files)}] Processing: {pdf_path.name}")

        for attempt_model in [model, FALLBACK_MODEL]:
            try:
                raw_output = call_gemini_with_pdf(client, pdf_path, attempt_model)
                if not raw_output.strip():
                    logger.warning(f"  Empty response from {attempt_model}")
                    continue

                qs = parse_gemini_output(raw_output, source_id)
                all_questions.extend(qs)
                processed_ids.add(source_id)

                logger.info(f"  Extracted {len(qs)} questions | Total: {len(all_questions)}")

                # Save after each PDF
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_questions, f, ensure_ascii=False, indent=2)
                break

            except Exception as e:
                err_str = str(e)
                if '503' in err_str or 'UNAVAILABLE' in err_str:
                    logger.warning(f"  {attempt_model} overloaded, trying fallback ...")
                    time.sleep(5)
                elif 'quota' in err_str.lower() or '429' in err_str:
                    logger.warning(f"  Rate limit hit, sleeping 30s ...")
                    time.sleep(30)
                else:
                    logger.error(f"  Error with {attempt_model}: {e}")
                    break

        time.sleep(3)  # polite delay between PDFs

    logger.info(f"\nDone. {len(all_questions)} OCR questions → {OUTPUT_FILE}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Max PDFs to process (0 = all)')
    parser.add_argument('--model', default=DEFAULT_MODEL, help='Gemini model to use')
    args = parser.parse_args()
    main(args.limit, args.model)
