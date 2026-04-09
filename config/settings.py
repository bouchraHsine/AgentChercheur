import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
PDF_DIR = DATA_DIR / "pdfs"

OUTPUTS_DIR = BASE_DIR / "outputs"

ARTICLES_JSON = OUTPUTS_DIR / "articles.json"
COMPARISON_MD = OUTPUTS_DIR / "comparison.md"
HYPOTHESES_MD = OUTPUTS_DIR / "hypotheses.md"
EXPERIMENTS_MD = OUTPUTS_DIR / "experiments.md"
REPORT_MD = OUTPUTS_DIR / "report.md"

def ensure_dirs():
    for p in [DATA_DIR, CACHE_DIR, PDF_DIR, OUTPUTS_DIR]:
        p.mkdir(parents=True, exist_ok=True)
