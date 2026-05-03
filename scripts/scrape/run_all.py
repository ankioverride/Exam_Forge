#!/usr/bin/env python3
"""
run_all.py — Master sequencer
Waits for QC to finish → generates UPSC/APSC → waits for OCR → pipeline merge.
Run this once; it handles everything.
"""
import subprocess, sys, time, logging, json
from pathlib import Path
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR.parent.parent / 'src' / 'data'

def run(cmd, desc=''):
    log.info(f'▶ {desc or " ".join(cmd)}')
    subprocess.run(cmd, cwd=str(SCRIPT_DIR), check=True)

def qc_still_running():
    """Check log file for completion marker — avoids wmic self-match bug."""
    log_path = SCRIPT_DIR / 'gemini_master.log'
    if not log_path.exists():
        return True  # hasn't started yet
    try:
        text = log_path.read_text(encoding='utf-8', errors='ignore')
        return '✓ All done.' not in text
    except:
        return True

def ocr_still_running():
    """Check if OCR log files show completion."""
    prelims_log = SCRIPT_DIR / 'gemini_prelims.log'
    official_log = SCRIPT_DIR / 'gemini_ocr_official.log'
    for log_path in [prelims_log, official_log]:
        if not log_path.exists():
            return True
        try:
            text = log_path.read_text(encoding='utf-8', errors='ignore')
            if 'Done.' not in text and 'done.' not in text:
                return True
        except:
            return True
    return False

def counts():
    r = {}
    for e in ['upsc', 'apsc', 'cat']:
        try:
            d = json.load(open(DATA_DIR / f'{e}.json', encoding='utf-8'))
            r[e] = Counter(q['subject'] for q in d)
        except:
            r[e] = Counter()
    return r

def log_counts(label):
    c = counts()
    log.info(f'\n=== {label} ===')
    for exam, subj in c.items():
        log.info(f'  {exam.upper()}: {sum(subj.values())} total')

# ─── Step 1: Wait for QC master to finish ────────────────────────────────────
log.info('Waiting for QC master to finish (check every 30s)...')
while qc_still_running():
    log.info('  QC still running...')
    time.sleep(30)
log.info('QC finished!')
log_counts('After QC')

# ─── Step 2: Generate UPSC weak subjects ─────────────────────────────────────
log.info('\nStep 2: Generate UPSC weak subjects')
run([sys.executable, 'gemini_master.py', '--phase', 'generate', '--exam', 'upsc'])

# ─── Step 3: Generate APSC weak subjects ─────────────────────────────────────
log.info('\nStep 3: Generate APSC weak subjects')
run([sys.executable, 'gemini_master.py', '--phase', 'generate', '--exam', 'apsc'])

# ─── Step 4: Wait for OCR jobs to finish ─────────────────────────────────────
log.info('\nStep 4: Waiting for OCR jobs to finish...')
while ocr_still_running():
    # Show progress
    for name in ['apsc_prelims_raw.json', 'apsc_official_raw.json']:
        path = SCRIPT_DIR / 'raw' / name
        if path.exists():
            try:
                d = json.load(open(path, encoding='utf-8'))
                log.info(f'  {name}: {len(d)} questions so far')
            except:
                pass
    time.sleep(60)
log.info('All OCR jobs finished!')

# ─── Step 5: Pipeline merge ───────────────────────────────────────────────────
log.info('\nStep 5: Run pipeline to merge all raw sources')
run([sys.executable, 'pipeline.py', '--exam', 'apsc'])
run([sys.executable, 'pipeline.py', '--exam', 'upsc'])

# ─── Final counts ─────────────────────────────────────────────────────────────
log_counts('FINAL')
log.info('\n✓ All done! Commit to GitHub next.')
