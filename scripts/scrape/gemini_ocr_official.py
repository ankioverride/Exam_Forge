#!/usr/bin/env python3
"""
Gemini OCR — Official APSC Papers from apsc.nic.in
Focuses on PRELIMS papers (100-150 MCQs each) + Sample booklets with answers.
Output: raw/apsc_official_raw.json
"""
import os, re, json, time, logging
from pathlib import Path
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('gemini_ocr_official.log', encoding='utf-8')])
log = logging.getLogger(__name__)

API_KEY = os.environ['GEMINI_API_KEY']
MODELS  = ['gemini-2.5-flash', 'gemini-2.5-pro']   # flash first — cheaper, fast

PDF_DIR     = Path(__file__).parent / 'raw' / 'apsc_official_pdfs'
OUTPUT_FILE = Path(__file__).parent / 'raw' / 'apsc_official_raw.json'
ANSWER_MAP  = {'A':0,'B':1,'C':2,'D':3,'a':0,'b':1,'c':2,'d':3,'1':0,'2':1,'3':2,'4':3}

APSC_SUBJECTS = {
    'Assam History':   ['ahom','lachit','saraighat','yandabo','sukaphaa','borphukan','maniram',
                        'moamoriya','burmese','koch','kachari','assam accord','phulaguri','kamarupa'],
    'Assam Geography': ['brahmaputra','barak','kaziranga','manas','majuli','kopili','subansiri',
                        'lohit','dibrugarh','tinsukia','kamrup','nagaon','karbi','golaghat','jorhat',
                        'sibsagar','guwahati','dhubri','cachar','darrang','sonitpur'],
    'Art & Culture':   ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi','ankiya',
                        'bhaona','ojapali','kamakhya','satra','rongali','kongali','bhogali',
                        'dhol','pepa','vaishnavism','madhabdev','name ghar'],
    'Polity':          ['sixth schedule','bodoland','assam accord','nrc','article 371','assam legislative',
                        'gauhati high court','btc','constitution','parliament','president','supreme court',
                        'governor','election','legislature','fundamental rights','directive'],
    'Economy':         ['digboi','oil india','numaligarh','ongc','assam tea','tea board','gdp','rbi',
                        'sebi','banking','budget','gst','assam silk','handloom','ril','nalco'],
    'Environment':     ['kaziranga','manas','orang','nameri','hoolock','golden langur','pygmy hog',
                        'greater adjutant','deepor beel','wildlife','forest','national park','rhino'],
    'History':         ['mughal','british','colonial','gandhi','nehru','congress','maurya','medieval',
                        'ancient','independence','revolt','dynasty','world war','partition'],
    'Science':         ['isro','space','chandrayaan','covid','vaccine','dna','technology','nuclear',
                        'physics','chemistry','biology','satellite','artificial intelligence'],
}

def classify(text: str) -> str:
    t = text.lower()
    scores = {s: sum(1 for kw in kws if kw in t) for s, kws in APSC_SUBJECTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'History'

# Specialised prompt for APSC Prelims — these have numbered MCQs with (A)(B)(C)(D) and answer keys
PRELIMS_PROMPT = """This is an official APSC (Assam Public Service Commission) CCE Preliminary Exam question paper.

Extract EVERY multiple choice question. For each output one JSON line:
{"q":"question text (no number prefix)","a":"option A","b":"option B","c":"option C","d":"option D","ans":"A","subj":"Polity"}

Subject classification for "subj" (choose ONE):
Assam History | Assam Geography | Art & Culture | History | Geography | Polity | Economy | Environment | Science

Rules:
- "ans" = A/B/C/D — use answer key if present; otherwise use your knowledge to determine the correct answer
- If options are unclear/missing in scan: generate 4 plausible options from your knowledge
- If question text is partially unclear: reconstruct it from context + options
- Remove question numbers from "q"
- Output ONLY JSON lines, no other text

Begin extraction:"""

SAMPLE_PROMPT = """This is an official APSC Sample Question Cum Answer Booklet.
It contains questions WITH their correct answers already marked/printed.

Extract every MCQ. For each output one JSON per line:
{"q":"question text","a":"option A text","b":"option B text","c":"option C text","d":"option D text","ans":"A"}

- "ans" = the correct answer letter (A/B/C/D) as shown in the booklet
- Remove question numbers from "q"
- Output ONLY JSON lines

Extract now:"""

def ocr_pdf(client, pdf_path: Path, is_sample: bool) -> list[dict]:
    prompt = SAMPLE_PROMPT if is_sample else PRELIMS_PROMPT
    log.info(f"  Uploading {pdf_path.name} ({pdf_path.stat().st_size//1024}KB)...")

    for model in MODELS:
        for attempt in range(3):
            try:
                with open(pdf_path, 'rb') as f:
                    uploaded = client.files.upload(
                        file=f,
                        config=types.UploadFileConfig(display_name=pdf_path.stem, mime_type='application/pdf')
                    )
                log.info(f"  Calling {model}...")
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_uri(file_uri=uploaded.uri, mime_type='application/pdf'),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=16384),
                )
                try: client.files.delete(name=uploaded.name)
                except: pass
                return parse(resp.text or '', pdf_path.stem)

            except Exception as e:
                err = str(e)
                try: client.files.delete(name=uploaded.name)
                except: pass
                if '503' in err or 'UNAVAILABLE' in err:
                    wait = (attempt+1)*15
                    log.warning(f"  {model} overloaded, waiting {wait}s...")
                    time.sleep(wait)
                elif '429' in err or 'quota' in err.lower():
                    log.warning(f"  Rate limit, sleeping 60s...")
                    time.sleep(60)
                else:
                    log.error(f"  {model} error: {err[:100]}")
                    break
    return []

def parse(raw: str, source_id: str) -> list[dict]:
    questions, seen = [], set()
    for line in raw.split('\n'):
        line = line.strip().strip('`')
        if not line.startswith('{'):
            continue
        try:
            obj = json.loads(line)
        except:
            try: obj = json.loads(re.sub(r',\s*}', '}', line))
            except: continue

        q = obj.get('q','').strip()
        if len(q) < 8: continue
        opts = [obj.get(k,'').strip() for k in ['a','b','c','d']]
        if any(len(o) < 1 for o in opts): continue

        ans = obj.get('ans','').strip().upper()
        correct = ANSWER_MAP.get(ans)
        if correct is None: continue   # skip if no answer

        norm = re.sub(r'\s+', ' ', q.lower())
        if norm in seen: continue
        seen.add(norm)

        raw_subj = obj.get('subj', '').strip()
        valid_subjects = {'Assam History','Assam Geography','Art & Culture','History',
                          'Geography','Polity','Economy','Environment','Science'}
        subject = raw_subj if raw_subj in valid_subjects else classify(q)

        questions.append({
            'id': f'official-{source_id}-{len(questions)}',
            'subject': subject,
            'difficulty': 'medium',
            'text': q,
            'options': opts,
            'correct': correct,
            'explanation': '',
            'source': f'apsc-official-{source_id}',
        })
    return questions

def main():
    client = genai.Client(api_key=API_KEY)

    # Load existing
    all_qs = []
    if OUTPUT_FILE.exists():
        all_qs = json.loads(OUTPUT_FILE.read_text(encoding='utf-8'))
        log.info(f"Loaded {len(all_qs)} existing")
    done_ids = {q['source'].split('apsc-official-')[-1] for q in all_qs}

    # Order: Prelims first (most MCQ-dense), then samples
    pdfs = sorted(PDF_DIR.glob('*.pdf'),
                  key=lambda p: (0 if 'CCEP' in p.name else 1, p.name))

    log.info(f"Processing {len(pdfs)} official APSC PDFs")

    for i, pdf in enumerate(pdfs):
        sid = pdf.stem
        if sid in done_ids:
            log.info(f"[{i+1}/{len(pdfs)}] {pdf.name}: already done, skipping")
            continue

        is_sample = 'SAMPLE' in pdf.name.upper()
        log.info(f"[{i+1}/{len(pdfs)}] {pdf.name} {'(sample+answers)' if is_sample else '(prelims MCQ)'}")

        qs = ocr_pdf(client, pdf, is_sample)
        all_qs.extend(qs)
        log.info(f"  Extracted {len(qs)} MCQs | Running total: {len(all_qs)}")

        OUTPUT_FILE.write_text(json.dumps(all_qs, ensure_ascii=False, indent=2), encoding='utf-8')
        time.sleep(4)

    log.info(f"\nDone. {len(all_qs)} total → {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
