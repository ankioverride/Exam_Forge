#!/usr/bin/env python3
"""
Gemini APSC Question Generator
--------------------------------
Uses Gemini 2.5 Pro to generate high-quality, fact-accurate MCQs for
APSC exam topics where our question bank is thin.

Generates in batches per subject and deduplicates against existing questions.

Usage:
    python gemini_generate.py
    python gemini_generate.py --subject "Art & Culture" --count 100
    python gemini_generate.py --subject all --count 80
"""

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
        logging.FileHandler('gemini_generate.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
MODEL          = 'gemini-2.5-pro'
FALLBACK_MODEL = 'gemini-2.5-flash'

RAW_DIR     = Path(__file__).parent / "raw"
OUTPUT_FILE = RAW_DIR / "gemini_apsc_raw.json"

ANSWER_MAP = {'A': 0, 'B': 1, 'C': 2, 'D': 3}

# Subject-specific context for better questions
SUBJECT_CONTEXT = {
    'Assam History': """
Assam History includes:
- Ahom Kingdom (1228–1826): Sukaphaa founded it, major kings like Suhungmung, Pratap Singha, Rudra Singha
- Battles: Battle of Saraighat (1671, Lachit Borphukan vs Mughals), Itakhuli, Alaboi
- Borphukans: Lachit Borphukan, Purnananda Burhagohain
- Koch Kingdom: Viswa Singha, Naranarayan, Chilarai
- Kachari, Chutia, Baro-Bhuiyans kingdoms
- British annexation: Treaty of Yandabo (1826), Bengal Province
- Anti-colonial movements: Phulaguri Dhawa (1861), Maniram Dewan (first tea planter, executed 1858)
- Assam Accord (1985): signed between Rajiv Gandhi and AASU
- NRC (National Register of Citizens), Article 371(B)
- Moamoria Rebellion (1769-1805)
- Cachar annexation, Jaintia Hills
""",
    'Assam Geography': """
Assam Geography includes:
- Rivers: Brahmaputra (enters Assam at Sadiya), Barak, Kopili, Subansiri, Lohit, Dibang, Jiabharali, Dhansiri, Jia Bhoroli
- Districts: 35 districts total; Kamrup Metropolitan, Kamrup Rural, Nagaon, Darrang, Sonitpur, Dibrugarh, Tinsukia, Jorhat, Sibsagar (now Sibasagar)
- Majuli: world's largest river island (in Brahmaputra)
- National Parks: Kaziranga, Manas, Nameri, Orang, Dibru-Saikhowa, Raimona
- Wildlife Sanctuaries: Pobitora, Deepor Beel, Laokhowa
- Hill districts: Karbi Anglong, Dima Hasao (NC Hills), Bodoland
- Geography: Assam Valley (Brahmaputra), Barak Valley, North Cachar Hills
- Border states: Arunachal Pradesh, Nagaland, Manipur, Mizoram, Tripura, Meghalaya, West Bengal
- Highest peak: Barail Range
""",
    'Art & Culture': """
Assam Art & Culture includes:
- Bihu festivals: Rongali (Bohag, April), Kongali (Kati, October), Bhogali (Magh, January)
- Sattriya dance: classical dance form by Srimanta Sankardeva (15th-16th century)
- Borgeet: devotional songs by Sankardeva and Madhavdeva
- Ankiya Naat: one-act plays performed in Sattra (monasteries)
- Ojapali: narrative singing tradition
- Muga silk: golden silk found only in Assam (Antheraea assamensis)
- Sualkuchi: silk weaving town, called 'Manchester of Assam'
- Srimanta Sankardeva: saint-scholar, founded Vaishnavism in Assam, created Nam Ghar (prayer house)
- Madhabdeva: disciple of Sankardeva
- Dhol, Pepa (buffalo-horn flute), Gogona, Taal, Khol: traditional instruments
- Bhaona: theatrical performance
- Gamocha: traditional Assamese towel/cloth
- Jaapi: traditional bamboo hat
""",
    'Polity': """
Assam/India Polity includes:
- Sixth Schedule: special provisions for tribal areas in Assam, Meghalaya, Tripura, Mizoram
- Bodoland Territorial Council (BTC): autonomous self-governing body
- Article 371(B): special provision for Assam
- Gauhati High Court: jurisdiction over Assam, Nagaland, Mizoram, Arunachal Pradesh
- Assam Legislative Assembly: 126 seats (as of current configuration)
- Rajya Sabha seats from Assam: 7
- Lok Sabha seats from Assam: 14
- Assam Accord 1985: ended Assam Agitation (1979-1985)
- AASU: All Assam Students Union
- AGP: Asom Gana Parishad (political party formed after Assam Accord)
- NRC: National Register of Citizens, updated 2019 in Assam
- CAA: Citizenship Amendment Act controversy
""",
    'Economy': """
Assam Economy includes:
- Tea: Assam produces ~52% of India's tea; major gardens in Upper Assam (Jorhat, Dibrugarh, Sivasagar)
- Oil: Digboi (first oil well in Asia, 1889), ONGC, Oil India Limited (HQ: Duliajan)
- Numaligarh Refinery (Golaghat), Bongaigaon Refinery, Digboi Refinery
- Coal: Makum coalfields (Tinsukia)
- Silk: Muga, Eri, Pat silk industries
- Agriculture: rice, jute, sugarcane
- Industries: Tea, Oil, Petrochemicals, Silk, Handloom
- GSDP and economic indicators
- Assam Gramin Vikash Bank, Assam Co-operative Apex Bank
- One District One Product (ODOP) scheme
""",
    'Environment': """
Assam Environment includes:
- Kaziranga National Park: UNESCO World Heritage Site, home to ~2600 one-horned rhinos (2/3 of world population), tigers, elephants
- Manas National Park: UNESCO World Heritage Site, Project Tiger, Project Elephant, Golden Langur
- Orang National Park (mini Kaziranga): one-horned rhinos, tigers
- Nameri National Park: elephants, tigers, Pati River
- Dibru-Saikhowa: feral horses, Gangetic river dolphin
- Raimona National Park: newest (2021), Golden Langur
- Deepor Beel: Ramsar wetland site, flamingos, migratory birds
- Hoolock Gibbon: India's only ape, found in Assam
- Pygmy Hog: smallest wild pig, Manas
- Greater Adjutant Stork: Dadara, Kamrup district
- Gangetic River Dolphin: state animal
- Himalayan Serow, Clouded Leopard also found
- Assam has ~37% forest cover
""",
}

# For general subjects (History, Science, Geography) that aren't Assam-specific
GENERAL_SUBJECT_CONTEXT = {
    'History': "Indian and World History relevant for APSC: ancient India, medieval India, Mughal period, British colonial period, freedom struggle, important personalities, important events.",
    'Science': "General Science relevant for APSC: physics, chemistry, biology, ISRO missions, recent scientific discoveries, environmental science, computer science basics.",
    'Geography': "Indian and World Geography: physical features, climate, soils, natural resources, economic geography, important rivers, mountains, and their relevance to India.",
}


def build_prompt(subject: str, count: int, existing_questions: list[str]) -> str:
    context = SUBJECT_CONTEXT.get(subject) or GENERAL_SUBJECT_CONTEXT.get(subject, '')
    existing_sample = '\n'.join(f'- {q}' for q in existing_questions[:20])

    return f"""You are creating MCQ questions for the APSC (Assam Public Service Commission) competitive exam.

SUBJECT: {subject}

CONTEXT / SYLLABUS:
{context}

ALREADY HAVE THESE QUESTIONS (do NOT repeat these or similar):
{existing_sample}

TASK: Generate exactly {count} unique, fact-accurate MCQ questions on {subject} suitable for APSC level.

FORMAT: Output each question as a JSON object on its own line:
{{"q": "question text", "a": "option A", "b": "option B", "c": "option C", "d": "option D", "ans": "X", "exp": "brief explanation"}}

Where:
- "ans" is exactly one of: A, B, C, D
- "exp" is 1-2 sentences explaining why the answer is correct
- All facts must be accurate and verifiable
- Questions should test knowledge not just recall — include "which of the following", "what is", "where is", "who was", "in which year" type questions
- Options should be plausible but only one correct
- Mix easy, medium, and hard difficulty

Output ONLY the JSON lines, nothing else. Generate all {count} questions now:
"""


def call_gemini(client, prompt: str, model: str = MODEL) -> str:
    for attempt_model in [model, FALLBACK_MODEL]:
        try:
            response = client.models.generate_content(
                model=attempt_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=16384,
                ),
            )
            return response.text or ''
        except Exception as e:
            err = str(e)
            if '503' in err or 'UNAVAILABLE' in err:
                logger.warning(f"  {attempt_model} overloaded, trying fallback ...")
                time.sleep(8)
            elif '429' in err or 'quota' in err.lower():
                logger.warning(f"  Rate limit, sleeping 60s ...")
                time.sleep(60)
                return call_gemini(client, prompt, attempt_model)
            else:
                logger.error(f"  Gemini error ({attempt_model}): {e}")
                if attempt_model == FALLBACK_MODEL:
                    raise
    return ''


def parse_response(raw: str, subject: str, source_id: str) -> list[dict]:
    questions = []
    seen = set()

    for line in raw.split('\n'):
        line = line.strip()
        if not line.startswith('{'):
            continue
        line = re.sub(r'```json?', '', line).strip('`').strip()
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            try:
                line = re.sub(r',\s*}', '}', line)
                obj = json.loads(line)
            except Exception:
                continue

        q_text = obj.get('q', '').strip()
        if len(q_text) < 10:
            continue

        opts = [obj.get(k, '').strip() for k in ['a', 'b', 'c', 'd']]
        if any(len(o) < 1 for o in opts):
            continue

        ans = obj.get('ans', '').strip().upper()
        correct_idx = ANSWER_MAP.get(ans)
        if correct_idx is None:
            continue

        exp = obj.get('exp', '').strip()

        norm = re.sub(r'\s+', ' ', q_text.lower())
        if norm in seen:
            continue
        seen.add(norm)

        questions.append({
            'id':          f"gen-{source_id}-{len(questions)}",
            'subject':     subject,
            'difficulty':  'medium',
            'text':        q_text,
            'options':     opts,
            'correct':     correct_idx,
            'explanation': exp,
            'source':      f'gemini-generated',
        })

    return questions


def main(target_subject: str, count_per_subject: int):
    client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info(f"Model: {MODEL}")

    # Load existing output
    all_questions = []
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        logger.info(f"Loaded {len(all_questions)} existing generated questions")

    # Load existing apsc.json to avoid duplicates
    apsc_path = Path(__file__).parent.parent.parent / 'src' / 'data' / 'apsc.json'
    existing_apsc = []
    if apsc_path.exists():
        with open(apsc_path, encoding='utf-8') as f:
            existing_apsc = json.load(f)

    # Determine subjects to generate
    all_subjects = list(SUBJECT_CONTEXT.keys()) + list(GENERAL_SUBJECT_CONTEXT.keys())
    if target_subject == 'all':
        subjects = all_subjects
    else:
        subjects = [target_subject]

    for subject in subjects:
        logger.info(f"\nGenerating {count_per_subject} questions for: {subject}")

        # Get existing questions for this subject to avoid duplicates
        existing_texts = [
            q['text'] for q in (existing_apsc + all_questions)
            if q.get('subject') == subject
        ]
        existing_count = len(existing_texts)
        logger.info(f"  Existing {subject} questions: {existing_count}")

        # Generate in batches of 50 to stay within token limits
        batch_size = 50
        batches = (count_per_subject + batch_size - 1) // batch_size
        batch_questions = []

        for batch in range(batches):
            remaining = count_per_subject - len(batch_questions)
            this_batch = min(batch_size, remaining)
            if this_batch <= 0:
                break

            logger.info(f"  Batch {batch+1}/{batches}: generating {this_batch} questions ...")
            prompt = build_prompt(subject, this_batch, existing_texts + [q['text'] for q in batch_questions])

            try:
                raw = call_gemini(client, prompt)
                new_qs = parse_response(raw, subject, f"{subject.replace(' ','_')}_{batch}")
                batch_questions.extend(new_qs)
                logger.info(f"  Batch {batch+1}: got {len(new_qs)} | Total for subject: {len(batch_questions)}")
                time.sleep(3)
            except Exception as e:
                logger.error(f"  Batch {batch+1} failed: {e}")
                break

        all_questions.extend(batch_questions)
        logger.info(f"  Done: {len(batch_questions)} new questions for {subject}")

        # Save after each subject
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=2)
        logger.info(f"  Saved. Total generated: {len(all_questions)}")

        time.sleep(5)

    logger.info(f"\nDone! {len(all_questions)} total generated questions → {OUTPUT_FILE}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject', default='all',
                        help='Subject to generate for, or "all"')
    parser.add_argument('--count', type=int, default=80,
                        help='Questions per subject')
    args = parser.parse_args()
    main(args.subject, args.count)
