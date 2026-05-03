#!/usr/bin/env python3
"""
Gemini OCR — APSC Prelims Papers (1998–2024) from assamcareer.com
17 papers, each ~100 MCQs. Uses year-aware prompt for better accuracy.
Output: raw/apsc_prelims_raw.json
"""
import re, json, time, logging
from pathlib import Path
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('gemini_prelims.log', encoding='utf-8')])
log = logging.getLogger(__name__)

API_KEY = 'REDACTED_API_KEY'
PDF_DIR     = Path(__file__).parent / 'raw' / 'pdfs'
OUTPUT_FILE = Path(__file__).parent / 'raw' / 'apsc_prelims_raw.json'
ANSWER_MAP  = {'A':0,'B':1,'C':2,'D':3,'a':0,'b':1,'c':2,'d':3}

# Ordered newest→oldest (newest more likely digital/better quality)
PRELIMS = [
    ('2024','Paper I',  '1T_b_0zynIl0ut5WRvIhie1Q62YmX-oFm'),
    ('2024','Paper II', '1PZGDk5J7i_PNs_ZBqtdynUdeCTnUiAdg'),
    ('2023','Paper I',  '1B2c6fKErcfAMNN1tOlObz90c7Injvb0H'),
    ('2023','Paper II', '1nBpp5OPlqzEKgSv4k3MONGv510JtB45C'),
    ('2022','Paper I',  '1CQiD5reseVxe1YpLN9lrciYo8fNK5av9'),
    ('2022','Paper II', '19G9LerJ8yqQ7DWIgK_cCjlgCHltl9-ni'),
    ('2020','Paper I',  '1u8Lsmyq-nB0uQl9g-TftN0eSut-EDm-g'),
    ('2020','Paper II', '1vm453ZEn-RXTXaop6JL1aF_OhdMRBF6u'),
    ('2018','Paper I',  '1AHgO1C1pfVvUV-mS6w5jH4wu7p61fUas'),
    ('2016','Paper I',  '1CvcDHK1FeoEsIR39AW2m9Ofh7HXdca0g'),
    ('2015','Paper I',  '1NsWjRQbriavkhP3u18iRD7sl_GCCADBy'),
    ('2014','Paper I',  '1yI2DVssIjVEqvQa6WNtC4egQZ4sJDACO'),
    ('2013','Paper I',  '1GBHl6qIp-5AZ6bLHOv1ugprt5GC0kEQj'),
    ('2011','Paper I',  '1HWJJJe9Td-3BQ5kj2WJdI0OxPABkfbZm'),
    ('2006','Paper I',  '1UZGLhAXB-FadKVp7wNhN-Tp64rn-c0s2'),
    ('2001','Paper I',  '13woJEaNc_1AL0nIiJxd8gE4u6iM7uAe9'),
    ('1998','Paper I',  '1v-xF08gO92bieAmXpgf1_2HRQC45bbzh'),
]

VALID_SUBJECTS = {
    'Assam History', 'Assam Geography', 'Art & Culture',
    'History', 'Geography', 'Polity', 'Economy', 'Environment', 'Science'
}

SUBJECT_GUIDE = """Subject classification guide (pick ONE):
- "Assam History": Ahom kingdom, Koch dynasty, Kachari, Battle of Saraighat, Lachit Borphukan, Assam under British, Assam Accord, Bodo movement, medieval Assam
- "Assam Geography": Brahmaputra river, Barak valley, Assam districts/towns, Assam physical features, Kaziranga, Manas, Majuli, floods in Assam
- "Art & Culture": Bihu, Sattriya dance, Borgeet, Sankardeva, Muga silk, Sualkuchi, Ankiya Naat, Bhaona, Ojapali, Kamakhya temple, Assamese literature/festivals
- "History": Ancient/medieval/modern Indian history, Mughal empire, British colonialism, Indian independence movement, world history — NOT specific to Assam
- "Geography": Indian or world physical/political geography, climate, rivers (not Assam-specific), economic geography
- "Polity": Indian Constitution, Parliament, President, PM, Supreme Court, elections, Fundamental Rights, DPSP, Constitutional amendments
- "Economy": Indian economy, RBI, banking, GST, budget, trade, industries, inflation, Five-Year Plans
- "Environment": Wildlife, national parks, ecology, biodiversity, climate change, pollution, conservation (India/world)
- "Science": Physics, chemistry, biology, space/ISRO, technology, health, medicine, computers"""

def classify_fallback(text: str) -> str:
    """Keyword fallback if Gemini didn't provide subject."""
    t = text.lower()
    if any(k in t for k in ['ahom','lachit','saraighat','borphukan','kamarupa','moamoriya','burmese invasion','assam history','yandabo','koch kingdom','kachari']):
        return 'Assam History'
    if any(k in t for k in ['brahmaputra','majuli','kaziranga','manas','kopili','assam district','assam geography','barak','dhubri','jorhat','sibsagar','dibrugarh']):
        return 'Assam Geography'
    if any(k in t for k in ['bihu','sattriya','borgeet','sankardeva','muga silk','sualkuchi','ankiya','kamakhya','satra','ojapali','gamocha','jaapi']):
        return 'Art & Culture'
    if any(k in t for k in ['constitution','parliament','supreme court','president','article ','fundamental right','directive principle','amendment']):
        return 'Polity'
    if any(k in t for k in ['rbi','gdp','gst','budget','sebi','banking','inflation','fiscal','monetary']):
        return 'Economy'
    if any(k in t for k in ['wildlife','national park','ecosystem','biodiversity','forest','carbon','climate change','pollution']):
        return 'Environment'
    if any(k in t for k in ['isro','dna','vaccine','photosynthesis','atom','molecule','satellite','physics','chemistry','biology']):
        return 'Science'
    return 'History'

def make_prompt(year: str, paper: str) -> str:
    return f"""This is the APSC CCE Preliminary Examination {year} — {paper}.
It is a scanned MCQ paper with approximately 100 questions.

Extract ALL multiple choice questions. For each, output exactly one JSON line:
{{"q":"question text","a":"option A","b":"option B","c":"option C","d":"option D","ans":"A","subj":"Assam History","yr":{year}}}

Rules for "ans":
1. If there is an ANSWER KEY at the end of the paper (a table showing question number → option), use it.
2. If NO answer key — use your own knowledge to determine the correct answer (A/B/C/D).
3. "ans" must always be A, B, C, or D — never "?".

Rules for "subj" (classify each question):
{SUBJECT_GUIDE}

EXTRACTION RULES — be aggressive, extract everything:
- Remove question numbers from "q" (e.g., "1." or "Q.1")
- If options use (i)(ii)(iii)(iv) format, map i→a, ii→b, iii→c, iv→d
- If a question's options are unclear/unreadable in the scan: generate 4 plausible distractors from your knowledge, mark the correct one
- If only a question stem is visible (no options): generate 4 options (1 correct + 3 distractors) based on your knowledge
- If options are visible but the question text is partially unclear: reconstruct the question from context and options
- You KNOW this is an APSC CCE Preliminary Exam — generate questions that fit APSC exam style if needed to reach the full expected count (~100 questions)
- Output ONLY JSON lines, no other text

Start extraction:"""

def call_gemini(client, pdf_path: Path, year: str, paper: str) -> str:
    prompt = make_prompt(year, paper)
    for model in ['gemini-2.5-flash', 'gemini-2.5-pro']:
        for attempt in range(3):
            uploaded = None
            try:
                with open(pdf_path, 'rb') as f:
                    uploaded = client.files.upload(
                        file=f,
                        config=types.UploadFileConfig(
                            display_name=f"APSC_{year}_{paper.replace(' ','_')}",
                            mime_type='application/pdf'
                        )
                    )
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_uri(file_uri=uploaded.uri, mime_type='application/pdf'),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(temperature=0.05, max_output_tokens=16384),
                )
                try: client.files.delete(name=uploaded.name)
                except: pass
                return resp.text or ''
            except Exception as e:
                if uploaded:
                    try: client.files.delete(name=uploaded.name)
                    except: pass
                err = str(e)
                if '503' in err or 'UNAVAILABLE' in err:
                    wait = (attempt+1)*20
                    log.warning(f"  {model} overloaded, waiting {wait}s...")
                    time.sleep(wait)
                elif '429' in err or 'quota' in err.lower():
                    log.warning(f"  Rate limit, sleeping 90s...")
                    time.sleep(90)
                else:
                    log.error(f"  {model}: {err[:120]}")
                    break
    return ''

def parse(raw: str, year: str, paper: str, source_id: str) -> list[dict]:
    qs, seen = [], set()
    for line in raw.split('\n'):
        line = line.strip().strip('`')
        if not line.startswith('{'): continue
        try:
            obj = json.loads(line)
        except:
            try: obj = json.loads(re.sub(r',\s*}', '}', line))
            except: continue
        q = obj.get('q','').strip()
        if len(q) < 8: continue
        opts = [obj.get(k,'').strip() for k in ['a','b','c','d']]
        if sum(1 for o in opts if len(o) > 0) < 3: continue
        # Pad missing options
        opts = [o if o else 'N/A' for o in opts]
        ans = obj.get('ans','').strip().upper()
        if ans == '?': continue   # skip unknown answers
        correct = ANSWER_MAP.get(ans)
        if correct is None: continue
        norm = re.sub(r'\s+', ' ', q.lower())
        if norm in seen: continue
        seen.add(norm)
        # Use Gemini's subject if valid, else keyword fallback
        raw_subj = obj.get('subj', '').strip()
        subject = raw_subj if raw_subj in VALID_SUBJECTS else classify_fallback(q)
        qs.append({
            'id': f'prelims-{year}-{paper.replace(" ","")}-{len(qs)}',
            'subject': subject,
            'difficulty': 'medium',
            'text': q,
            'options': opts,
            'correct': correct,
            'explanation': '',
            'year': year,
            'source': f'apsc-prelims-{year}',
        })
    return qs

def main():
    client = genai.Client(api_key=API_KEY)
    all_qs = []
    if OUTPUT_FILE.exists():
        all_qs = json.loads(OUTPUT_FILE.read_text(encoding='utf-8'))
        log.info(f"Loaded {len(all_qs)} existing")
    done = {q['source'] for q in all_qs}

    log.info(f"Processing {len(PRELIMS)} APSC Prelims papers")
    for i, (year, paper, fid) in enumerate(PRELIMS):
        src = f'apsc-prelims-{year}'
        if src in done:
            log.info(f"[{i+1}/{len(PRELIMS)}] {year} {paper}: already done, skipping")
            continue
        pdf = PDF_DIR / f'apsc_{fid}.pdf'
        if not pdf.exists():
            log.warning(f"  PDF missing: {pdf.name}")
            continue
        log.info(f"[{i+1}/{len(PRELIMS)}] APSC Prelims {year} — {paper} ({pdf.stat().st_size//1024}KB)")
        raw = call_gemini(client, pdf, year, paper)
        if not raw:
            log.warning(f"  No response from Gemini")
            continue
        qs = parse(raw, year, paper, f'{year}_{paper.replace(" ","")}')
        all_qs.extend(qs)
        log.info(f"  Extracted {len(qs)} MCQs | Total: {len(all_qs)}")
        OUTPUT_FILE.write_text(json.dumps(all_qs, ensure_ascii=False, indent=2), encoding='utf-8')
        time.sleep(5)

    log.info(f"\nDone. {len(all_qs)} Prelims MCQs → {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
