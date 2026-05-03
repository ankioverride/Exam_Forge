#!/usr/bin/env python3
"""
Post-QC Runner — runs automatically after QC finishes.
Handles: generation for UPSC/APSC + pipeline merge.
Run this after gemini_master.py --phase qc completes.
"""
import subprocess, sys, json, logging
from pathlib import Path
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR.parent.parent / 'src' / 'data'

def counts():
    r = {}
    for e in ['upsc','apsc','cat']:
        d = json.load(open(DATA_DIR/f'{e}.json', encoding='utf-8'))
        r[e] = Counter(q['subject'] for q in d)
    return r

def run(cmd):
    log.info(f'▶ {" ".join(cmd)}')
    subprocess.run(cmd, cwd=str(SCRIPT_DIR), check=True)

if __name__ == '__main__':
    log.info('=== POST-QC RUNNER ===')
    c = counts()
    log.info('Current counts:')
    for exam, subj in c.items():
        log.info(f'  {exam.upper()}: {sum(subj.values())} total')

    # 1. Generate UPSC (overwritten by QC race)
    log.info('\nStep 1: Generate UPSC subjects to target')
    run([sys.executable, 'gemini_master.py', '--phase', 'generate', '--exam', 'upsc'])

    # 2. Generate APSC (overwritten by QC race) + merge raw files
    log.info('\nStep 2: Generate APSC subjects to target')
    run([sys.executable, 'gemini_master.py', '--phase', 'generate', '--exam', 'apsc'])

    # 3. Merge all raw sources via pipeline (OCR + generated raw)
    log.info('\nStep 3: Merge raw files into apsc.json via pipeline')
    run([sys.executable, 'pipeline.py', '--exam', 'apsc'])

    # 4. Final counts
    c2 = counts()
    log.info('\n=== FINAL COUNTS ===')
    for exam, subj in c2.items():
        log.info(f'{exam.upper()}: {sum(subj.values())} total')
        for s, n in sorted(subj.items()):
            log.info(f'  {s:<35} {n}')

    log.info('\nAll done! Commit to GitHub next.')
