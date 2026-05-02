# ExamForge Question Scraper

Scrapes MCQ questions from public sources and merges them into the question banks at `src/data/`.

## Sources

| Source | What | Exam |
|--------|------|------|
| IndiaBix.com | GK, QA, VA, LR, DI — hundreds of pages, static HTML | UPSC, CAT, APSC |
| GKToday.in | UPSC Prelims PYQs (2010–2024), year-wise | UPSC |
| 2IIM.com | CAT previous year papers with solutions | CAT |
| GKToday Assam | Assam GK quiz pages | APSC |

---

## Setup

```bash
cd examprep/scripts/scrape
pip install -r requirements.txt
```

---

## Step 1 — Scrape IndiaBix (bulk questions, ~1000–2000 per exam)

```bash
# Scrape all exams (takes 1–2 hours, rate-limited to be polite)
python indiabix_scraper.py --exam all

# Or per exam:
python indiabix_scraper.py --exam upsc
python indiabix_scraper.py --exam cat
python indiabix_scraper.py --exam apsc

# Test run (2 pages per category only, ~5 minutes):
python indiabix_scraper.py --exam upsc --max-pages 2
```

Output: `raw/upsc_raw.json`, `raw/cat_raw.json`, `raw/apsc_raw.json`

**Resumable** — if interrupted, re-run the same command. It resumes from the last saved checkpoint.

---

## Step 2 — Scrape PYQs (2010–2024)

```bash
python pyq_scraper.py --exam all

# Or per exam:
python pyq_scraper.py --exam upsc   # GKToday UPSC Prelims papers
python pyq_scraper.py --exam cat    # 2IIM CAT papers
python pyq_scraper.py --exam apsc   # Assam GK
```

Output: `raw/pyq_upsc_raw.json`, `raw/pyq_cat_raw.json`, `raw/pyq_apsc_raw.json`

---

## Step 3 — Merge into src/data/

```bash
# Dry run — see stats without writing files
python pipeline.py --stats

# Write merged output to src/data/
python pipeline.py --exam all
```

The pipeline:
- Validates every question (4 options, correct index 0–3, valid subject/difficulty)
- Deduplicates (exact + ~80% word overlap near-duplicate detection)
- Assigns sequential IDs (continues from last existing ID)
- Merges with existing questions, preserving all manually written ones

---

## Expected yields (approximate)

| Exam | IndiaBix | PYQs | Total target |
|------|----------|------|--------------|
| UPSC | ~1,500   | ~300 | **1,800+**   |
| CAT  | ~2,000   | ~200 | **2,200+**   |
| APSC | ~400     | ~100 | **500+**      |

---

## Notes

- Rate limited: 1.5–3.5s between pages, 3–6s between categories
- All scrapers save checkpoints after every page — safe to interrupt
- `raw/` files are intermediate — not committed to git
- Only `src/data/*.json` is committed
- Questions with missing/unparseable answers are automatically dropped by the pipeline
