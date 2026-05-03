#!/usr/bin/env python3
"""
CAT Mock Test Telegram Scraper + Gemini OCR
--------------------------------------------
Downloads PDFs from public Telegram channels containing CAT mock papers,
then uses Gemini Vision to extract MCQs from scanned pages.

Requires:
    pip install telethon google-genai
    GEMINI_API_KEY env var set

Usage:
    python cat_mock_tg_scraper.py
    python cat_mock_tg_scraper.py --channel mock_mock_mock_2026 --limit 500
    python cat_mock_tg_scraper.py --ocr-only    # skip Telegram, OCR already-downloaded PDFs
"""

import os
import re
import json
import time
import asyncio
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
        logging.FileHandler('cat_mock_tg.log', encoding='utf-8'),
    ]
)
log = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
MODEL          = 'gemini-2.5-flash'

RAW_DIR    = Path(__file__).parent / 'raw'
PDF_DIR    = RAW_DIR / 'cat_mock_pdfs'
OUTPUT     = RAW_DIR / 'cat_mock_tg_raw.json'
RAW_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

API_ID   = int(os.environ.get('TELEGRAM_API_ID',   '31711700'))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '1d02c841923121e145e3ecd44c095e07')

TARGET_CHANNELS = [
    'mock_mock_mock_2026',
]

SECTION_MAP = {
    'qa':   'Quantitative Aptitude',
    'quant': 'Quantitative Aptitude',
    'quantitative': 'Quantitative Aptitude',
    'va':   'Verbal Ability',
    'varc': 'Verbal Ability',
    'verbal': 'Verbal Ability',
    'di':   'Data Interpretation',
    'lr':   'Logical Reasoning',
    'dilr': 'Data Interpretation',  # will assign DI/LR by question position
}

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}


def make_prompt(filename: str) -> str:
    return f"""This is a CAT (Common Admission Test) mock paper PDF: {filename}

Extract EVERY multiple-choice question. For each question output exactly one JSON line:
{{"q":"question text","a":"option A text","b":"option B text","c":"option C text","d":"option D text","ans":"B","sec":"Quantitative Aptitude"}}

Rules:
- "sec" must be exactly one of: "Quantitative Aptitude", "Verbal Ability", "Data Interpretation", "Logical Reasoning"
- "ans" must be A, B, C, or D
  - Use the answer key if present in the paper
  - Otherwise use your knowledge to determine the correct answer
- For Data Interpretation / DILR sets: extract each sub-question separately with the same section label
- Include the DI table/chart description in the question text if needed for context
- If a question has 5 options, only include A-D
- Skip questions that are purely reading comprehension passages (no MCQ)
- Do NOT output any text outside the JSON lines

Output only JSON lines, one per question, nothing else."""


def parse_response(text: str, pdf_name: str) -> list[dict]:
    questions = []
    seen = set()

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Try to fix truncated lines
            try:
                obj = json.loads(line + '"}}')
            except Exception:
                continue

        q = obj.get('q', '').strip()
        if len(q) < 10:
            continue

        opts = [
            str(obj.get('a', '')).strip(),
            str(obj.get('b', '')).strip(),
            str(obj.get('c', '')).strip(),
            str(obj.get('d', '')).strip(),
        ]
        if any(len(o) < 1 for o in opts):
            continue

        ans_raw = str(obj.get('ans', '')).strip().upper()
        correct = ANSWER_MAP.get(ans_raw)
        if correct is None:
            continue

        # Deduplicate
        key = re.sub(r'\s+', ' ', q.lower())[:80]
        if key in seen:
            continue
        seen.add(key)

        # Section
        sec_raw = str(obj.get('sec', '')).strip()
        section = sec_raw if sec_raw in {
            'Quantitative Aptitude', 'Verbal Ability',
            'Data Interpretation', 'Logical Reasoning'
        } else 'Quantitative Aptitude'

        import hashlib
        file_hash = hashlib.md5(pdf_name.encode()).hexdigest()[:8]
        uid = f"catmock-{file_hash}-{len(questions)}"
        questions.append({
            'id':          uid,
            'subject':     section,
            'difficulty':  'hard',
            'text':        q,
            'options':     opts,
            'correct':     correct,
            'explanation': '',
            'source':      f'cat-mock-{pdf_name[:40]}',
        })

    return questions


def ocr_pdf(pdf_path: Path, client: genai.Client) -> list[dict]:
    """Upload PDF to Gemini Files API and extract MCQs."""
    log.info(f'  OCR: {pdf_path.name}')

    try:
        # Upload file
        with open(pdf_path, 'rb') as f:
            uploaded = client.files.upload(
                file=f,
                config=types.UploadFileConfig(
                    mime_type='application/pdf',
                    display_name=pdf_path.name,
                )
            )
        log.info(f'    Uploaded → {uploaded.name}')

        # Wait for processing
        for _ in range(20):
            file_info = client.files.get(name=uploaded.name)
            if file_info.state.name == 'ACTIVE':
                break
            time.sleep(3)
        else:
            log.warning(f'    File {uploaded.name} not ACTIVE after 60s')
            return []

        prompt = make_prompt(pdf_path.name)
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_uri(file_uri=uploaded.uri, mime_type='application/pdf'),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=16000,
            ),
        )

        # Clean up file
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass

        raw = response.text or ''
        qs = parse_response(raw, pdf_path.name)
        log.info(f'    Extracted {len(qs)} questions')
        return qs

    except Exception as e:
        log.error(f'    OCR failed for {pdf_path.name}: {e}')
        return []


async def download_pdfs_from_channel(channel: str, limit: int) -> list[Path]:
    """Download PDF documents from a Telegram channel."""
    downloaded = []
    try:
        from telethon import TelegramClient
    except ImportError:
        log.error('telethon not installed: pip install telethon')
        return []

    session_path = Path(__file__).parent / 'apsc_session'

    client = TelegramClient(str(session_path), API_ID, API_HASH)
    async with client:
        log.info(f'Connected to Telegram')
        try:
            entity = await client.get_entity(channel)
            log.info(f'Scanning @{channel} (up to {limit} messages)…')

            async for msg in client.iter_messages(entity, limit=limit):
                if not msg.document:
                    continue
                mime = getattr(msg.document, 'mime_type', '') or ''
                fname = ''
                for attr in (msg.document.attributes or []):
                    if hasattr(attr, 'file_name'):
                        fname = attr.file_name or ''

                is_pdf = mime == 'application/pdf' or fname.lower().endswith('.pdf')
                if not is_pdf:
                    continue

                safe = re.sub(r'[^\w\-.]', '_', fname or f'doc_{msg.id}')
                if not safe.endswith('.pdf'):
                    safe += '.pdf'
                dest = PDF_DIR / f'{channel}_{msg.id}_{safe}'

                if dest.exists() and dest.stat().st_size > 1000:
                    log.info(f'  Already have: {dest.name}')
                    downloaded.append(dest)
                    continue

                log.info(f'  Downloading: {fname or msg.id}')
                try:
                    await client.download_media(msg, file=str(dest))
                    await asyncio.sleep(1.5)
                    if dest.exists() and dest.stat().st_size > 1000:
                        downloaded.append(dest)
                except Exception as e:
                    log.warning(f'  Download failed: {e}')

        except Exception as e:
            log.error(f'Channel error @{channel}: {e}')

    log.info(f'Downloaded {len(downloaded)} PDFs from @{channel}')
    return downloaded


def main(channels: list[str], limit: int, ocr_only: bool):
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Load existing
    all_qs = []
    if OUTPUT.exists():
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            all_qs = json.load(f)
    existing_ids = {q['id'] for q in all_qs}
    log.info(f'Existing: {len(all_qs)} CAT mock questions')

    # Collect PDFs
    pdfs: list[Path] = []
    if ocr_only:
        pdfs = sorted(PDF_DIR.glob('*.pdf'))
        log.info(f'OCR-only mode: {len(pdfs)} PDFs in {PDF_DIR}')
    else:
        for channel in channels:
            new_pdfs = asyncio.run(download_pdfs_from_channel(channel, limit))
            pdfs.extend(new_pdfs)

    if not pdfs:
        log.info('No PDFs to process.')
        return

    # Track already-processed PDFs by name
    processed_file = RAW_DIR / 'cat_mock_processed.json'
    processed = set()
    if processed_file.exists():
        processed = set(json.loads(processed_file.read_text(encoding='utf-8')))

    # OCR each PDF
    added = 0
    for pdf_path in pdfs:
        if pdf_path.name in processed:
            log.info(f'  Already processed: {pdf_path.name}')
            continue

        qs = ocr_pdf(pdf_path, client)
        new_qs = [q for q in qs if q['id'] not in existing_ids]
        for q in new_qs:
            existing_ids.add(q['id'])
        all_qs.extend(new_qs)
        added += len(new_qs)
        processed.add(pdf_path.name)

        # Save after each PDF
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(all_qs, f, ensure_ascii=False, indent=2)
        processed_file.write_text(json.dumps(sorted(processed), indent=2), encoding='utf-8')
        log.info(f'  Saved. Total: {len(all_qs)} (+{len(new_qs)} new)')

        time.sleep(2)  # rate limit

    log.info(f'\nDone. Added {added} new questions. Total: {len(all_qs)}')
    log.info(f'Output: {OUTPUT}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--channels', nargs='+', default=TARGET_CHANNELS)
    parser.add_argument('--limit', type=int, default=1000,
                        help='Messages per channel to scan')
    parser.add_argument('--ocr-only', action='store_true',
                        help='Skip Telegram download, OCR already-downloaded PDFs')
    args = parser.parse_args()
    main(args.channels, args.limit, args.ocr_only)
